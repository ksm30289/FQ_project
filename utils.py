import hashlib
from typing import Any, Dict, Optional

from config import FILE_DEDUP_MODE


def _safe_str(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def make_row_hash(
    date: str,
    time: str,
    user: str,
    message: str,
    source_file_name: str = "",
) -> str:
    """
    raw_chat row 중복 제거용 해시
    같은 날짜/시간/유저/메시지/원본파일명이면 동일 row로 간주
    """
    raw = "|".join(
        [
            _safe_str(date),
            _safe_str(time),
            _safe_str(user),
            _safe_str(message),
            _safe_str(source_file_name),
        ]
    )
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()


def make_file_key(file_meta: Dict[str, Any], mode: Optional[str] = None) -> str:
    """
    파일 중복 제거용 키 생성

    지원 모드
    - id
    - name
    - md5
    - size_name
    - name_size   (하위호환)
    - none        (사실상 매번 다른 값 반환)
    - 기타/기본   -> id|name|size
    """
    selected_mode = _safe_str(mode or FILE_DEDUP_MODE).lower()

    file_id = _safe_str(file_meta.get("id"))
    file_name = _safe_str(file_meta.get("name"))
    file_size = _safe_str(file_meta.get("size"))
    md5_checksum = _safe_str(
        file_meta.get("md5Checksum") or file_meta.get("md5")
    )

    if selected_mode == "none":
        raw = f"{file_id}|{file_name}|{file_size}|{md5_checksum}"
        return hashlib.sha1(raw.encode("utf-8")).hexdigest()

    if selected_mode == "id":
        return file_id

    if selected_mode == "name":
        return file_name

    if selected_mode == "md5":
        return md5_checksum or f"{file_name}|{file_size}"

    if selected_mode in ("size_name", "name_size"):
        return f"{file_name}|{file_size}"

    # fallback
    return f"{file_id}|{file_name}|{file_size}"
