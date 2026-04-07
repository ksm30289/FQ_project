from config import (
    FILE_DEDUP_MODE,
    MAX_FILES_PER_RUN,
    ROW_DEDUP_ENABLED,
    DEBUG_LOG,
    AI_REVIEW_ENABLED,
)
from drive_client import GoogleDriveClient
from parser import parse_chat_text
from sheets import GoogleSheetClient
from utils import make_file_key
from trend_classifier import classify_and_write_trends


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

    print(f"[INFO] 조회된 txt 파일 수: {len(files)}")
    if not files:
        print("[INFO] 처리할 txt 파일이 없습니다.")
        return

    total_files = 0
    total_raw_rows = 0
    total_classified = 0

    for file_meta in files:
        file_id = file_meta["id"]
        file_name = file_meta["name"]
        file_key = make_file_key(file_meta)

        print(f"\n=== 파일 처리 시작: {file_name} ===")

        if FILE_DEDUP_MODE and file_key in processed_file_keys:
            print(f"[SKIP] 이미 처리된 파일: {file_name}")
            continue

        try:
            text = drive_client.download_txt_file(file_id)
            print(f"[INFO] 파일 다운로드 완료: {file_name} / {len(text)} chars")

            parsed_rows = parse_chat_text(
                text=text,
                source_file=file_name,
                existing_row_hashes=existing_row_hashes,
            )

            print(f"[INFO] 파싱 결과 row 수: {len(parsed_rows)}")

            if not parsed_rows:
                print("[INFO] 신규 raw_chat row 없음")
                if FILE_DEDUP_MODE:
                    sheet_client.mark_file_processed(file_key, file_name)
                    print("[OK] 처리 완료 파일 기록 저장")
                continue

            # raw_chat 저장
            sheet_client.append_raw_rows(parsed_rows)
            print(f"[OK] raw_chat 저장 완료: {len(parsed_rows)}건")
            total_raw_rows += len(parsed_rows)

            # 이번 런에서 추가된 row_hash도 즉시 반영
            if ROW_DEDUP_ENABLED:
                for row in parsed_rows:
                    row_hash = row.get("row_hash")
                    if row_hash:
                        existing_row_hashes.add(row_hash)

            # AI 분류
            if AI_REVIEW_ENABLED:
                try:
                    classified_count = classify_and_write_trends(sheet_client, parsed_rows)
                    print(f"[OK] AI 분류 저장 완료: {classified_count}건")
                    total_classified += classified_count
                except Exception as e:
                    print(f"[ERROR] AI 분류 단계 실패: {e}")
            else:
                print("[INFO] AI_REVIEW_ENABLED=false 이므로 AI 분류 생략")

            # 처리 완료 파일 기록
            if FILE_DEDUP_MODE:
                sheet_client.mark_file_processed(file_key, file_name)
                print("[OK] 처리 완료 파일 기록 저장")

            total_files += 1

        except Exception as e:
            print(f"[ERROR] 파일 처리 실패 - {file_name}: {e}")

    print("\n=== 작업 종료 ===")
    print(f"[SUMMARY] 처리 파일 수: {total_files}")
    print(f"[SUMMARY] raw_chat 저장 row 수: {total_raw_rows}")
    print(f"[SUMMARY] 분류 저장 row 수: {total_classified}")


if __name__ == "__main__":
    main()
