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
# Railway에는 credentials.json 파일 대신 JSON 문자열을 환경변수로 저장
GOOGLE_CREDENTIALS_JSON = _required_env("GOOGLE_CREDENTIALS_JSON")


def get_google_credentials_dict() -> Dict[str, Any]:
    try:
        return json.loads(GOOGLE_CREDENTIALS_JSON)
    except json.JSONDecodeError as e:
        raise RuntimeError("GOOGLE_CREDENTIALS_JSON 값이 올바른 JSON이 아닙니다.") from e


# ===== Google Sheets =====
SPREADSHEET_ID = _required_env("SPREADSHEET_ID")
WORKSHEET_NAME = os.getenv("WORKSHEET_NAME", "raw_chat")
DEDUP_WORKSHEET_NAME = os.getenv("DEDUP_WORKSHEET_NAME", "_dedupe_keys")
FILE_DEDUP_WORKSHEET_NAME = os.getenv("FILE_DEDUP_WORKSHEET_NAME", "_processed_files")

# raw_chat 헤더 기준 권장:
# datetime | user | message | row_hash
RAW_CHAT_HEADERS = ["datetime", "user", "message", "row_hash"]

# ===== Google Drive =====
# txt가 업로드되는 폴더
DRIVE_SOURCE_FOLDER_ID = _required_env("DRIVE_SOURCE_FOLDER_ID")

# 처리 완료 후 이동할 폴더(권장)
DRIVE_PROCESSED_FOLDER_ID = os.getenv("DRIVE_PROCESSED_FOLDER_ID", "").strip()

# 처리할 확장자
ALLOWED_EXTENSIONS = [".txt"]

# ===== 파서 관련 =====
DEFAULT_ROOM_NAME = os.getenv("DEFAULT_ROOM_NAME", "오픈채팅")
IGNORE_SYSTEM_MESSAGES = _get_bool_env("IGNORE_SYSTEM_MESSAGES", "true")

# 제외할 사용자명
# 예: EXCLUDED_USERNAMES=오픈채팅봇,테스트봇
EXCLUDED_USERNAMES = _get_csv_set_env("EXCLUDED_USERNAMES", "오픈채팅봇")

# ===== 처리 옵션 =====
WRITE_HEADER_IF_EMPTY = True

# Railway에서는 대용량 파일 처리 시 1~2개부터 시작 권장
MAX_FILES_PER_RUN = _get_int_env("MAX_FILES_PER_RUN", "1")

# 파일 중복 방지 기준
# 권장값:
# - "file" : file_key 기준 중복 방지
# - "id"   : Drive file id 기준
# - "name_size" : 파일명 + 파일크기 기준
FILE_DEDUP_MODE = os.getenv("FILE_DEDUP_MODE", "file").strip().lower()

# row 중복 제거 활성화
ROW_DEDUP_ENABLED = _get_bool_env("ROW_DEDUP_ENABLED", "true")

# 처리 완료 파일을 별도 폴더로 이동할지 여부
MOVE_PROCESSED_FILE = _get_bool_env("MOVE_PROCESSED_FILE", "false")

# 상세 로그 출력 여부
DEBUG_LOG = _get_bool_env("DEBUG_LOG", "true")

# ===== AI 검수 =====
OPENAI_API_KEY = _required_env("OPENAI_API_KEY")
AI_REVIEW_ENABLED = _get_bool_env("AI_REVIEW_ENABLED", "true")
AI_REVIEW_MODEL = os.getenv("AI_REVIEW_MODEL", "gpt-4.1-mini").strip()

# AI 검수 배치 크기 (너무 크게 잡으면 느려짐)
AI_REVIEW_BATCH_SIZE = _get_int_env("AI_REVIEW_BATCH_SIZE", "20")
