from pathlib import Path

from config import UPLOAD_DIR, ENCODINGS
from parser import parse_chat_file
from sheets import GoogleSheetClient
from utils import read_text_with_fallback, make_row_hash


def build_row_hash(row: dict) -> str:
    # 파일명이 달라도 같은 메시지 중복 업로드를 어느 정도 막고 싶으면 source_file 제외 가능
    return make_row_hash(
        row["room_name"],
        row["datetime"],
        row["user_name"],
        row["message"],
    )


def collect_txt_files(upload_dir: Path) -> list[Path]:
    return sorted(upload_dir.glob("*.txt"))


def main():
    if not UPLOAD_DIR.exists():
        raise FileNotFoundError(f"업로드 폴더가 없습니다: {UPLOAD_DIR}")

    files = collect_txt_files(UPLOAD_DIR)
    if not files:
        print("처리할 txt 파일이 없습니다.")
        return

    sheet_client = GoogleSheetClient()
    existing_hashes = sheet_client.get_existing_hashes()

    total_parsed = 0
    total_uploaded = 0

    for file_path in files:
        print(f"[처리 시작] {file_path.name}")

        try:
            text = read_text_with_fallback(file_path, ENCODINGS)
            parsed_rows = parse_chat_file(file_path, text)
            total_parsed += len(parsed_rows)

            new_rows = []
            for row in parsed_rows:
                row_hash = build_row_hash(row)
                row["row_hash"] = row_hash

                if row_hash not in existing_hashes:
                    new_rows.append(row)
                    existing_hashes.add(row_hash)

            uploaded_count = sheet_client.append_chat_rows(new_rows)
            total_uploaded += uploaded_count

            print(
                f"[완료] {file_path.name} | "
                f"parsed={len(parsed_rows)} | uploaded={uploaded_count}"
            )

        except Exception as e:
            print(f"[에러] {file_path.name}: {e}")

    print("=" * 60)
    print(f"총 파싱 건수: {total_parsed}")
    print(f"총 업로드 건수: {total_uploaded}")
    print("작업 완료")


if __name__ == "__main__":
    main()
