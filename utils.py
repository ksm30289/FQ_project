import hashlib
from typing import Iterable, List


def make_sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def make_row_hash(room_name: str, dt: str, user_name: str, message: str) -> str:
    raw = "||".join([
        (room_name or "").strip(),
        (dt or "").strip(),
        (user_name or "").strip(),
        (message or "").strip(),
    ])
    return make_sha256(raw)


def make_file_key(file_id: str, file_name: str, file_size: str, mode: str = "id") -> str:
    if mode == "id":
        return file_id
    return make_sha256(f"{file_name}||{file_size}")


def chunked(data: List, size: int) -> Iterable[List]:
    for i in range(0, len(data), size):
        yield data[i:i + size]
