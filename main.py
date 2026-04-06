from config import FILE_DEDUP_MODE, MAX_FILES_PER_RUN
from drive_client import GoogleDriveClient
from parser import parse_chat_text
from sheets import GoogleSheetClient
from utils import make_file_key, make_row_hash


def main():
    print("=== 작업 시작 ===")

    drive_client = GoogleDriveClient()
    sheet_client = GoogleSheetClient()

    existing_row_hashes = sheet_client.get_existing_row_hashes()
    processed_file_keys = sheet_client.get_processed_file_keys()

    files = drive_client.list_txt_files(limit=MAX_FILES_PER_RUN)
    if not files:
        print("처리할 txt 파일이 없습니다.")
        return

    total_files = 0
    total_rows = 0
    total_uploaded = 0

    for file_meta in files:
        file_id = file_meta["id"]
        file_name = file_meta["name"]
        file_size = str(file_meta.get("size", "0"))

        file_key = make_file_key(file_id, file_name, file_size, mode=FILE_DEDUP_MODE)

        if file_key in processed_file_keys:
            print(f"[SKIP] 이미 처리한 파일: {file_name}")
            continue

        print(f"[FILE] 처리 시작: {file_name}")

        try:
            text = drive_client.download_text_file(file_id)
            parsed_rows = parse_chat_text(
                text=text,
                source_file=file_name,
                room_name=file_name.rsplit(".", 1)[0],
            )

            new_rows = []
            for row in parsed_rows:
                row_hash = make_row_hash(
                    room_name=row["room_name"],
                    dt=row["datetime"],
                    user_name=row["user_name"],
                    message=row["message"],
                )
                row["row_hash"] = row_hash

                if row_hash not in existing_row_hashes:
                    existing_row_hashes.add(row_hash)
                    new_rows.append(row)

            uploaded_count = sheet_client.append_chat_rows(new_rows)
            sheet_client.mark_file_processed(file_key, file_id, file_name, file_size)
            drive_client.move_to_processed(file_id)

            total_files += 1
            total_rows += len(parsed_rows)
            total_uploaded += uploaded_count

            print(
                f"[DONE] {file_name} | parsed={len(parsed_rows)} | uploaded={uploaded_count}"
            )

        except Exception as e:
            print(f"[ERROR] {file_name}: {e}")

    print("=== 작업 종료 ===")
    print(f"처리 파일 수: {total_files}")
    print(f"총 파싱 행 수: {total_rows}")
    print(f"총 업로드 행 수: {total_uploaded}")


if __name__ == "__main__":
    main()
