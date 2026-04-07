import hashlib
import re
from typing import Any, Dict, Optional

from config import FILE_DEDUP_MODE


def _safe_str(value: Any) -> str:
    if value is None:
        return ""
    value = str(value)

    # 🔥 핵심: 문자열 정규화 (숨은 중복 방지)
    value = value.replace("\r\n", "\n").replace("\r", "\n")
    value = value.replace("\u200b", "")  # zero-width space 제거
    value = re.sub(r"[ \t]+", " ", value)
    value = re.sub(r"\n+", "\n", value)

    return value.strip()


def make_row_hash(
    date: str,
    time: str,
    user: str,
    message: str,
    source_file_name: str = "",  # ← 유지하되 사용 안함
) -> str:
    """
    raw_chat row 중복 제거용 해시

    ⚠️ 중요:
    source_file_name은 절대 포함하면 안됨
    (같은 메시지가 다른 파일에 있을 수 있기 때문)
    """

    raw = "|".join(
        [
            _safe_str(date),
            _safe_str(time),
            _safe_str(user),
            _safe_str(message),
        ]
    )

    return hashlib.sha1(raw.encode("utf-8")).hexdigest()


def make_file_key(file_meta: Dict[str, Any], mode: Optional[str] = None) -> str:
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

    return f"{file_id}|{file_name}|{file_size}"
