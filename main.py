from config import FILE_DEDUP_MODE, MAX_FILES_PER_RUN
from drive_client import GoogleDriveClient
from parser import parse_chat_text
from sheets import GoogleSheetClient, RAW_CHAT_SHEET, PROCESSED_FILES_SHEET, RAW_HEADERS
from utils import make_file_key
from trend_classifier import (
    TREND_HEADERS,
    classify_message,
    make_trend_row,
)

TREND_SHEETS = ["negative_trend", "positive_trend", "suggestions"]


def read_txt_file_flexible(drive_client, file_id: str) -> str:
    method_candidates = [
        "download_text_file",
        "download_txt_file",
        "read_txt_file",
        "get_file_text",
        "download_file_text",
        "read_file_text",
        "get_txt_file_content",
        "download_file_content",
        "get_file_content",
    ]

    for method_name in method_candidates:
        if hasattr(drive_client, method_name):
            method = getattr(drive_client, method_name)
            content = method(file_id)

            if isinstance(content, bytes):
                return content.decode("utf-8-sig", errors="replace")

            return str(content)

    raise AttributeError(
        "GoogleDriveClient에서 txt 본문을 읽는 메서드를 찾지 못했습니다. "
        "download_text_file / download_txt_file / read_txt_file / get_file_text 중 하나로 맞춰주세요."
    )


def row_dict_to_raw_row_list(row: dict) -> list:
    return [
        row.get("room_name", ""),
        row.get("source_file", ""),
        row.get("datetime", ""),
        row.get("date", ""),
        row.get("time", ""),
        row.get("user_name", ""),
        row.get("message", ""),
        row.get("row_hash", ""),
    ]


def main():
    print("=== 작업 시작 ===")

    drive_client = GoogleDriveClient()
    sheet_client = GoogleSheetClient()

    # 시트 준비
    sheet_client.ensure_sheet(RAW_CHAT_SHEET, RAW_HEADERS)
    sheet_client.ensure_sheet(PROCESSED_FILES_SHEET, ["file_key"])

    for trend_sheet in TREND_SHEETS:
        sheet_client.ensure_sheet(trend_sheet, TREND_HEADERS)

    # 기존 중복 데이터 로딩
    existing_row_hashes = sheet_client.get_existing_row_hashes(RAW_CHAT_SHEET)
    processed_file_keys = sheet_client.get_processed_file_keys(PROCESSED_FILES_SHEET)

    print("[STEP] Drive 파일 조회 시작")

    try:
        files = drive_client.list_txt_files(limit=MAX_FILES_PER_RUN)
        print("[STEP] Drive 파일 조회 완료")
        print(f"[DEBUG] Drive 파일 수: {len(files)}")
    except Exception as e:
        print(f"[ERROR] Drive 파일 조회 실패: {e}")
        raise

    print(f"[DEBUG] Drive에서 찾은 파일 수: {len(files)}")
    for f in files:
        print(f"[DEBUG] 파일: {f['name']} (id={f['id']}, size={f.get('size', '0')})")

    if not files:
        print("처리할 txt 파일이 없습니다.")
        return

    total_files = 0
    total_rows = 0
    total_uploaded = 0
    processed_file_keys_to_append = []

    for file_meta in files:
        file_id = file_meta["id"]
        file_name = file_meta["name"]
        file_key = make_file_key(
            file_meta["id"],
            file_meta["name"],
            file_meta.get("size", "0"),
            mode=FILE_DEDUP_MODE
        )

        if file_key in processed_file_keys:
            print(f"[SKIP] 이미 처리한 파일: {file_name}")
            continue

        print(f"[INFO] 파일 처리 시작: {file_name}")

        try:
            raw_text = read_txt_file_flexible(drive_client, file_id)
            parsed_rows = parse_chat_text(raw_text, file_name)
        except Exception as e:
            print(f"[ERROR] 파일 파싱 실패: {file_name} / {e}")
            continue

        if not parsed_rows:
            print(f"[WARN] 파싱 결과 없음: {file_name}")
            processed_file_keys_to_append.append(file_key)
            total_files += 1
            continue

        raw_rows_to_upload = []
        categorized_rows = {
            "negative_trend": [],
            "positive_trend": [],
            "suggestions": [],
        }

        file_uploaded_count = 0

        for row in parsed_rows:
            row_hash = row.get("row_hash", "").strip()
            if not row_hash:
                continue

            if row_hash in existing_row_hashes:
                continue

            raw_rows_to_upload.append(row_dict_to_raw_row_list(row))
            existing_row_hashes.add(row_hash)
            file_uploaded_count += 1

            classified = classify_message(row.get("message", ""))

            for sheet_name, keywords in classified.items():
                categorized_rows[sheet_name].append(make_trend_row(row, keywords))

        try:
            if raw_rows_to_upload:
                sheet_client.append_rows(RAW_CHAT_SHEET, raw_rows_to_upload)

            for sheet_name in TREND_SHEETS:
                if categorized_rows[sheet_name]:
                    sheet_client.append_rows(sheet_name, categorized_rows[sheet_name])

            processed_file_keys_to_append.append(file_key)
            processed_file_keys.add(file_key)

            # 처리 후 폴더 이동
            try:
                drive_client.move_to_processed(file_id)
            except Exception as e:
                print(f"[WARN] 처리완료 폴더 이동 실패: {file_name} / {e}")

            total_files += 1
            total_rows += len(parsed_rows)
            total_uploaded += file_uploaded_count

            print(
                f"[INFO] 파일 처리 완료: {file_name} / "
                f"parsed={len(parsed_rows)} / uploaded={file_uploaded_count} / "
                f"negative={len(categorized_rows['negative_trend'])} / "
                f"positive={len(categorized_rows['positive_trend'])} / "
                f"suggestions={len(categorized_rows['suggestions'])}"
            )

        except Exception as e:
            print(f"[ERROR] 시트 업로드 실패: {file_name} / {e}")

    if processed_file_keys_to_append:
        try:
            sheet_client.append_processed_file_keys(
                processed_file_keys_to_append,
                PROCESSED_FILES_SHEET
            )
        except Exception as e:
            print(f"[ERROR] processed_files 기록 실패: {e}")

    print("=== 작업 종료 ===")
    print(f"처리 파일 수: {total_files}")
    print(f"파싱 행 수: {total_rows}")
    print(f"업로드 행 수(raw_chat 기준): {total_uploaded}")


if __name__ == "__main__":
    main()
