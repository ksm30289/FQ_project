from config import (
    FILE_DEDUP_MODE,
    MAX_FILES_PER_RUN,
    ROW_DEDUP_ENABLED,
    DEBUG_LOG,
)
from drive_client import GoogleDriveClient
from parser import parse_chat_text
from sheets import GoogleSheetClient
from utils import make_file_key


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
    print("[STEP] Drive 파일 조회 완료")

    log_debug(f"[DEBUG] Drive에서 찾은 파일 수: {len(files)}")
    for f in files:
        log_debug(
            f"[DEBUG] 파일: {f['name']} "
            f"(id={f['id']}, size={f.get('size', '0')})"
        )

    if not files:
        print("처리할 txt 파일이 없습니다.")
        return

    total_files = 0
    total_parsed = 0
    total_uploaded = 0

    for file_meta in files:
        file_id = file_meta["id"]
        file_name = file_meta["name"]
        modified_time = file_meta.get("modifiedTime", "")

        file_key = make_file_key(file_id, file_name, modified_time)

        if FILE_DEDUP_MODE == "file" and file_key in processed_file_keys:
            print(f"[SKIP] 이미 처리한 파일: {file_name}")
            continue

        print(f"[INFO] 파일 처리 시작: {file_name}")

        try:
            print(f"[STEP] 파일 다운로드 시작: {file_name}")
            text = drive_client.download_txt_file(file_id)
            log_debug(f"[DEBUG] 파일 길이(char): {len(text)}")

            print(f"[STEP] 파싱 시작: {file_name}")
            parsed_rows = parse_chat_text(text)
            log_debug(f"[DEBUG] 파싱 완료: {len(parsed_rows)} rows")

            total_parsed += len(parsed_rows)

            print(f"[STEP] 중복 제거 + 업로드 row 생성: {file_name}")
            upload_rows = sheet_client.build_raw_rows_for_upload(
                parsed_rows,
                existing_row_hashes,
            )
            log_debug(f"[DEBUG] 업로드 대상 row 수: {len(upload_rows)}")

            if upload_rows:
                print(f"[STEP] 시트 배치 업로드 시작: {file_name}")
                sheet_client.append_raw_rows_batch(upload_rows)
                print(f"[STEP] 시트 배치 업로드 완료: {file_name}")
            else:
                print(f"[INFO] 업로드할 신규 row 없음: {file_name}")

            if FILE_DEDUP_MODE == "file":
                sheet_client.append_processed_file_key(file_key)
                processed_file_keys.add(file_key)

            drive_client.move_file_to_processed(file_id)

            total_files += 1
            total_uploaded += len(upload_rows)

            print(
                f"[DONE] 파일 처리 완료: {file_name} | "
                f"parsed={len(parsed_rows)}, uploaded={len(upload_rows)}"
            )

        except Exception as e:
            print(f"[ERROR] 파일 처리 실패: {file_name} | {e}")

    print("=== 작업 종료 ===")
    print(f"[SUMMARY] 처리 파일 수: {total_files}")
    print(f"[SUMMARY] 파싱 행 수: {total_parsed}")
    print(f"[SUMMARY] 업로드 행 수: {total_uploaded}")


if __name__ == "__main__":
    main()
