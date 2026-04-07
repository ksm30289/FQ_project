import json
import os
from typing import Any, Dict


def _required_env(name: str) -> str:
    value = os.getenv(name)
    if value is None or str(value).strip() == "":
        raise RuntimeError(f"환경변수 누락: {name}")
    return value.strip()


def _get_env(name: str, default: str) -> str:
    value = os.getenv(name)
    if value is None or str(value).strip() == "":
        return default
    return value.strip()


def _get_bool_env(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return str(value).strip().lower() in ("1", "true", "yes", "y", "on")


def _get_int_env(name: str, default: int) -> int:
    value = os.getenv(name)
    if value is None or str(value).strip() == "":
        return default
    try:
        return int(str(value).strip())
    except ValueError:
        raise RuntimeError(f"정수 환경변수 형식 오류: {name}={value}")


def _get_float_env(name: str, default: float) -> float:
    value = os.getenv(name)
    if value is None or str(value).strip() == "":
        return default
    try:
        return float(str(value).strip())
    except ValueError:
        raise RuntimeError(f"실수 환경변수 형식 오류: {name}={value}")


def _get_list_env(name: str, default: list[str]) -> list[str]:
    value = os.getenv(name)
    if value is None or str(value).strip() == "":
        return default

    raw = str(value).strip()

    if raw.startswith("[") and raw.endswith("]"):
        try:
            parsed = json.loads(raw)
            if isinstance(parsed, list):
                return [str(x).strip() for x in parsed if str(x).strip()]
        except json.JSONDecodeError:
            pass

    return [item.strip() for item in raw.split(",") if item.strip()]


def get_google_credentials_dict() -> Dict[str, Any]:
    raw = _required_env("GOOGLE_CREDENTIALS")

    try:
        creds = json.loads(raw)
    except json.JSONDecodeError:
        repaired = raw.replace("\\n", "\n")
        try:
            creds = json.loads(repaired)
        except json.JSONDecodeError as e:
            raise RuntimeError(f"GOOGLE_CREDENTIALS JSON 파싱 실패: {e}")

    if not isinstance(creds, dict):
        raise RuntimeError("GOOGLE_CREDENTIALS 형식 오류: JSON object 여야 합니다.")

    required_keys = [
        "type",
        "project_id",
        "private_key_id",
        "private_key",
        "client_email",
        "client_id",
        "token_uri",
    ]
    missing = [k for k in required_keys if k not in creds or not creds[k]]
    if missing:
        raise RuntimeError(f"GOOGLE_CREDENTIALS 필수 키 누락: {missing}")

    creds["private_key"] = str(creds["private_key"]).replace("\\n", "\n")
    return creds


# =========================
# Google Sheets / Drive
# =========================
SPREADSHEET_ID = _required_env("SPREADSHEET_ID")

WORKSHEET_NAME = _get_env("WORKSHEET_NAME", "raw_chat")
FILE_DEDUP_WORKSHEET_NAME = _get_env("FILE_DEDUP_WORKSHEET_NAME", "file_dedup")

NEGATIVE_TREND_WORKSHEET_NAME = _get_env("NEGATIVE_TREND_WORKSHEET_NAME", "부정 동향")
POSITIVE_TREND_WORKSHEET_NAME = _get_env("POSITIVE_TREND_WORKSHEET_NAME", "긍정 동향")
SUGGESTIONS_WORKSHEET_NAME = _get_env("SUGGESTIONS_WORKSHEET_NAME", "건의")
TREND_WORKSHEET_NAME = _get_env("TREND_WORKSHEET_NAME", "디스코드 동향")

WRITE_HEADER_IF_EMPTY = _get_bool_env("WRITE_HEADER_IF_EMPTY", True)


# =========================
# 파서 옵션
# =========================
IGNORE_SYSTEM_MESSAGES = _get_bool_env("IGNORE_SYSTEM_MESSAGES", True)
EXCLUDED_USERNAMES = _get_list_env("EXCLUDED_USERNAMES", ["오픈채팅봇"])


# =========================
# 처리 옵션
# =========================
DEBUG_LOG = _get_bool_env("DEBUG_LOG", True)
MAX_FILES_PER_RUN = _get_int_env("MAX_FILES_PER_RUN", 100)

# none / name / id / md5 / size_name
FILE_DEDUP_MODE = _get_env("FILE_DEDUP_MODE", "size_name")

# raw_chat row_hash 중복 제거
ROW_DEDUP_ENABLED = _get_bool_env("ROW_DEDUP_ENABLED", True)


# =========================
# AI 리뷰 옵션
# =========================
AI_REVIEW_ENABLED = _get_bool_env("AI_REVIEW_ENABLED", True)
AI_MIN_CONFIDENCE = _get_float_env("AI_MIN_CONFIDENCE", 0.80)
AI_MAX_RETRIES = _get_int_env("AI_MAX_RETRIES", 3)
AI_RETRY_SLEEP_SEC = _get_float_env("AI_RETRY_SLEEP_SEC", 1.2)

OPENAI_MODEL = _get_env("OPENAI_MODEL", "gpt-4o-mini")
AI_REVIEW_WORKERS = _get_int_env("AI_REVIEW_WORKERS", 8)
AI_REVIEW_PARALLEL_ENABLED = _get_bool_env("AI_REVIEW_PARALLEL_ENABLED", True)


# =========================
# Header 정의
# main.py / sheets.py 와 일치해야 함
# =========================
RAW_CHAT_HEADERS = [
    "date",
    "time",
    "user",
    "message",
    "source_file_name",
    "row_hash",
]

TREND_HEADERS = [
    "date",
    "time",
    "user",
    "message",
    "source_file_name",
    "category",
    "confidence",
    "reason",
    "row_hash",
]
