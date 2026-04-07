import hashlib


def make_file_key(file_id: str, file_name: str, modified_time: str = "") -> str:
    raw = f"{file_id}|{file_name}|{modified_time}"
    return hashlib.md5(raw.encode("utf-8")).hexdigest()


def make_row_hash(dt: str, user: str, message: str) -> str:
    # 긴 메시지도 비교 빠르게 하려고 해시 사용
    raw = f"{dt}|{user}|{message}"
    return hashlib.md5(raw.encode("utf-8")).hexdigest()
