import hashlib

from config import FILE_DEDUP_MODE


def make_row_hash(datetime_str: str, user: str, message: str) -> str:
    raw = f"{datetime_str}|{user}|{message}".strip()
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()


def make_file_key(file_meta: dict) -> str:
    """
    file_meta 예시:
    {
        "id": "...",
        "name": "...",
        "size": "1234"
    }
    """
    mode = FILE_DEDUP_MODE

    file_id = str(file_meta.get("id", "")).strip()
    file_name = str(file_meta.get("name", "")).strip()
    file_size = str(file_meta.get("size", "")).strip()

    if mode == "id":
        return file_id

    if mode == "name_size":
        return f"{file_name}|{file_size}"

    # 기본: file
    return f"{file_id}|{file_name}|{file_size}"
