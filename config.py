import json
import os
from typing import Any, Dict


def _required_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"환경변수 누락: {name}")
    return value


# ===== Google 인증 =====
# Railway에는 credentials.json 파일 대신 JSON 문자열을 환경변수로 저장
GOOGLE_CREDENTIALS_JSON = _required_env("GOOGLE_CREDENTIALS_JSON")


def get_google_credentials_dict() -> Dict[str, Any]:
    try:
        return json.loads(GOOGLE_CREDENTIALS_JSON)
    except json.JSONDecodeError as e:
        raise RuntimeError("GOOGLE_CREDENTIALS_JSON 값이 올바른 JSON이 아닙니다.") from e


# ===== Google Sheets =====
SPREADSHEET_NAME = _required_env("SPREADSHEET_NAME")
WORKSHEET_NAME = os.getenv("WORKSHEET_NAME", "raw_chat")
DEDUP_WORKSHEET_NAME = os.getenv("DEDUP_WORKSHEET_NAME", "_dedupe_keys")
FILE_DEDUP_WORKSHEET_NAME = os.getenv("FILE_DEDUP_WORKSHEET_NAME", "_processed_files")

# ===== Google Drive =====
# txt가 업로드되는 폴더
DRIVE_SOURCE_FOLDER_ID = _required_env("DRIVE_SOURCE_FOLDER_ID")

# 처리 완료 후 이동할 폴더(권장)
DRIVE_PROCESSED_FOLDER_ID = os.getenv("DRIVE_PROCESSED_FOLDER_ID", "")

# 처리할 확장자
ALLOWED_EXTENSIONS = [".txt"]

# ===== 파서 관련 =====
DEFAULT_ROOM_NAME = os.getenv("DEFAULT_ROOM_NAME", "오픈채팅")
IGNORE_SYSTEM_MESSAGES = os.getenv("IGNORE_SYSTEM_MESSAGES", "true").lower() == "true"

# ===== 처리 옵션 =====
WRITE_HEADER_IF_EMPTY = True
MAX_FILES_PER_RUN = int(os.getenv("MAX_FILES_PER_RUN", "20"))

# 파일 중복 방지 기준
# id : Drive file id 기준
# name_size : 파일명 + 파일크기 기준
FILE_DEDUP_MODE = os.getenv("FILE_DEDUP_MODE", "id")
