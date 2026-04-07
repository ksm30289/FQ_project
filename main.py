from config import (
    FILE_DEDUP_MODE,
    MAX_FILES_PER_RUN,
    ROW_DEDUP_ENABLED,
    DEBUG_LOG,
)
from drive_client import GoogleDriveClient
from parser import parse_chat_text
from sheets import GoogleSheetClient
from utils import make_file_key, make_row_hash
from ai_reviewer import review_message_with_ai
from trend_classifier import classify_row_with_ai_result


def log_debug(message: str):
    if DEBUG_LOG:
        print(message)


def main():
    print("=== 작업 시작 ===")

    drive_client = GoogleDriveClient()
    sheet_client = GoogleSheetClient()

    if ROW_DEDUP_ENABLED:
        print("[STEP] 기존 row_hash 조회 시작")
        existing_row_hashes = sheet_client.get_existing_row_hashes()
        log_debug(f"[DEBUG] 기존 row_hash 수: {len(existing_row_hashes)}")
    else:
        existing_row_hashes = set()
        print("[STEP] row 중복 제거 비활성화 상태")

    print("[STEP] 처리 완료 파일키 조회 시작")
    processed_file_keys = sheet_client.get_processed_file_keys()
    log_debug(f"[DEBUG] 처리 완료 파일키 수: {len(processed_file_keys)}")

    print("[STEP] Drive 파일 조회 시작")
    files = drive_client.list_txt_files(limit=MAX_FILES_PER_RUN)

    print(f"[INFO] Drive 조회 파일 수: {len(files)}")
    if not files:
        print("처리할 txt 파일이 없습니다.")
        return

    total_files = 0
    total_parsed_rows = 0
    total_raw_uploaded = 0
    total_ai_routed = 0
    total_ignored = 0

    raw_rows_buffer = []
    routed_rows_by_sheet = {
        "긍정 동향": [],
        "부정 동향": [],
        "건의": [],
        "디스코드 동향": [],
    }
    processed_file_keys_to_add = []

    for file_meta in files:
        file_id = file_meta["id"]
        file_name = file_meta["name"]
        file_key = make_file_key(file_meta)

        if FILE_DEDUP_MODE != "none" and file_key in processed_file_keys:
            print(f"[SKIP] 이미 처리한 파일: {file_name}")
            continue

        print(f"[FILE] 처리 시작: {file_name}")

        try:
            text = drive_client.download_txt_file(file_id)
            parsed_rows = parse_chat_text(text, source_file_name=file_name)
        except Exception as e:
            print(f"[ERROR] 파일 처리 실패: {file_name} / {e}")
            continue

        if not parsed_rows:
            print(f"[SKIP] 파싱 결과 없음: {file_name}")
            if FILE_DEDUP_MODE != "none":
                processed_file_keys_to_add.append([file_key, file_name])
            continue

        total_files += 1
        total_parsed_rows += len(parsed_rows)

        file_new_raw_count = 0
        file_routed_count = 0
        file_ignored_count = 0

        for row in parsed_rows:
            row_hash = make_row_hash(row)

            if ROW_DEDUP_ENABLED and row_hash in existing_row_hashes:
                continue

            # 1) raw_chat 저장용 버퍼
            raw_rows_buffer.append([
                row.get("date", ""),
                row.get("time", ""),
                row.get("user", ""),
                row.get("message", ""),
                row.get("source_file_name", file_name),
                row_hash,
            ])
            file_new_raw_count += 1
            total_raw_uploaded += 1

            if ROW_DEDUP_ENABLED:
                existing_row_hashes.add(row_hash)

            # 2) AI 분류
            message = row.get("message", "")
            ai_result = review_message_with_ai(message)

            target_sheet = classify_row_with_ai_result(ai_result)

            if target_sheet is None:
                file_ignored_count += 1
                total_ignored += 1
                continue

            routed_rows_by_sheet[target_sheet].append([
                row.get("date", ""),
                row.get("time", ""),
                row.get("user", ""),
                row.get("message", ""),
                row.get("source_file_name", file_name),
                ai_result.get("category", ""),
                ai_result.get("confidence", ""),
                ai_result.get("reason", ""),
                row_hash,
            ])
            file_routed_count += 1
            total_ai_routed += 1

        if FILE_DEDUP_MODE != "none":
            processed_file_keys_to_add.append([file_key, file_name])

        print(
            f"[DONE] {file_name} | "
            f"parsed={len(parsed_rows)}, raw={file_new_raw_count}, "
            f"routed={file_routed_count}, ignored={file_ignored_count}"
        )

    # 3) 배치 저장
    print("[STEP] raw_chat 저장 시작")
    if raw_rows_buffer:
        sheet_client.append_raw_rows(raw_rows_buffer)
        print(f"[INFO] raw_chat 저장 완료: {len(raw_rows_buffer)}건")
    else:
        print("[INFO] raw_chat 저장할 데이터 없음")

    print("[STEP] 분류 시트 저장 시작")
    for sheet_name, rows in routed_rows_by_sheet.items():
        if rows:
            sheet_client.append_classified_rows(sheet_name, rows)
            print(f"[INFO] {sheet_name} 저장 완료: {len(rows)}건")
        else:
            print(f"[INFO] {sheet_name} 저장할 데이터 없음")

    print("[STEP] 파일 dedup 기록 저장 시작")
    if processed_file_keys_to_add:
        sheet_client.append_processed_file_keys(processed_file_keys_to_add)
        print(f"[INFO] 처리 파일 기록 저장 완료: {len(processed_file_keys_to_add)}건")
    else:
        print("[INFO] 추가 처리 파일 기록 없음")

    print("=== 작업 완료 ===")
    print(f"처리 파일 수: {total_files}")
    print(f"파싱 행 수: {total_parsed_rows}")
    print(f"raw_chat 저장 수: {total_raw_uploaded}")
    print(f"분류 저장 수: {total_ai_routed}")
    print(f"ignore 수: {total_ignored}")


if __name__ == "__main__":
    main()
