import json
import os
from typing import Any, Dict, Set


def _required_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"환경변수 누락: {name}")
    return value


def _get_bool_env(name: str, default: str = "false") -> bool:
    return os.getenv(name, default).strip().lower() == "true"


def _get_int_env(name: str, default: str) -> int:
    value = os.getenv(name, default).strip()
    try:
        return int(value)
    except ValueError as e:
        raise RuntimeError(f"환경변수 {name} 값이 정수가 아닙니다: {value}") from e


def _get_csv_set_env(name: str, default: str = "") -> Set[str]:
    raw = os.getenv(name, default)
    return {item.strip() for item in raw.split(",") if item.strip()}


# ===== Google 인증 =====
GOOGLE_CREDENTIALS_JSON = _required_env("GOOGLE_CREDENTIALS_JSON")


def get_google_credentials_dict() -> Dict[str, Any]:
    try:
        return json.loads(GOOGLE_CREDENTIALS_JSON)
    except json.JSONDecodeError as e:
        raise RuntimeError("GOOGLE_CREDENTIALS_JSON 값이 올바른 JSON이 아닙니다.") from e


# ===== Google Sheets =====
SPREADSHEET_ID = _required_env("SPREADSHEET_ID")

WORKSHEET_NAME = os.getenv("WORKSHEET_NAME", "raw_chat").strip()
DEDUP_WORKSHEET_NAME = os.getenv("DEDUP_WORKSHEET_NAME", "_dedupe_keys").strip()
FILE_DEDUP_WORKSHEET_NAME = os.getenv("FILE_DEDUP_WORKSHEET_NAME", "_processed_files").strip()

NEGATIVE_TREND_WORKSHEET_NAME = os.getenv("NEGATIVE_TREND_WORKSHEET_NAME", "negative_trend").strip()
POSITIVE_TREND_WORKSHEET_NAME = os.getenv("POSITIVE_TREND_WORKSHEET_NAME", "positive_trend").strip()
SUGGESTIONS_WORKSHEET_NAME = os.getenv("SUGGESTIONS_WORKSHEET_NAME", "suggestions").strip()

# raw_chat 시트 헤더
RAW_CHAT_HEADERS = ["datetime", "user", "message", "row_hash", "source_file"]

# AI 분류 시트 헤더
TREND_HEADERS = ["datetime", "user", "message", "source_file", "reason", "row_hash"]

WRITE_HEADER_IF_EMPTY = True

# ===== Google Drive =====
DRIVE_SOURCE_FOLDER_ID = _required_env("DRIVE_SOURCE_FOLDER_ID")
DRIVE_PROCESSED_FOLDER_ID = os.getenv("DRIVE_PROCESSED_FOLDER_ID", "").strip()
ALLOWED_EXTENSIONS = [".txt"]

# ===== 파서 관련 =====
DEFAULT_ROOM_NAME = os.getenv("DEFAULT_ROOM_NAME", "오픈채팅")
IGNORE_SYSTEM_MESSAGES = _get_bool_env("IGNORE_SYSTEM_MESSAGES", "true")
EXCLUDED_USERNAMES = _get_csv_set_env("EXCLUDED_USERNAMES", "오픈채팅봇")

# ===== 처리 옵션 =====
MAX_FILES_PER_RUN = _get_int_env("MAX_FILES_PER_RUN", "1")

# 권장값: file / id / name_size
FILE_DEDUP_MODE = os.getenv("FILE_DEDUP_MODE", "file").strip().lower()

ROW_DEDUP_ENABLED = _get_bool_env("ROW_DEDUP_ENABLED", "true")
MOVE_PROCESSED_FILE = _get_bool_env("MOVE_PROCESSED_FILE", "false")
DEBUG_LOG = _get_bool_env("DEBUG_LOG", "true")

# ===== AI 검수 =====
OPENAI_API_KEY = _required_env("OPENAI_API_KEY")
AI_REVIEW_ENABLED = _get_bool_env("AI_REVIEW_ENABLED", "true")
AI_REVIEW_MODEL = os.getenv("AI_REVIEW_MODEL", "gpt-4.1-mini").strip()
AI_REVIEW_BATCH_SIZE = _get_int_env("AI_REVIEW_BATCH_SIZE", "20")
