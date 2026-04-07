import time
from typing import Any, Dict, List, Set

import gspread
from google.oauth2.service_account import Credentials

from config import (
    SPREADSHEET_ID,
    WORKSHEET_NAME,
    FILE_DEDUP_WORKSHEET_NAME,
    NEGATIVE_TREND_WORKSHEET_NAME,
    POSITIVE_TREND_WORKSHEET_NAME,
    SUGGESTIONS_WORKSHEET_NAME,
    TREND_WORKSHEET_NAME,
    WRITE_HEADER_IF_EMPTY,
    RAW_CHAT_HEADERS,
    TREND_HEADERS,
    DEBUG_LOG,
    get_google_credentials_dict,
)

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

FILE_DEDUP_HEADERS = [
    "file_id",
    "file_name",
    "file_key",
]


def log_debug(message: str) -> None:
    if DEBUG_LOG:
        print(message)


class GoogleSheetClient:
    def __init__(self):
        creds_info = get_google_credentials_dict()
        creds = Credentials.from_service_account_info(creds_info, scopes=SCOPES)
        self.gc = gspread.authorize(creds)

        self.spreadsheet_id = SPREADSHEET_ID
        self.sh = self.gc.open_by_key(self.spreadsheet_id)

        self.raw_sheet = self._get_or_create_worksheet(WORKSHEET_NAME)
        self.file_dedup_sheet = self._get_or_create_worksheet(FILE_DEDUP_WORKSHEET_NAME)
        self.negative_sheet = self._get_or_create_worksheet(NEGATIVE_TREND_WORKSHEET_NAME)
        self.positive_sheet = self._get_or_create_worksheet(POSITIVE_TREND_WORKSHEET_NAME)
        self.suggestions_sheet = self._get_or_create_worksheet(SUGGESTIONS_WORKSHEET_NAME)
        self.trend_sheet = self._get_or_create_worksheet(TREND_WORKSHEET_NAME)

        self._ensure_all_headers()

    # =========================================================
    # Worksheet 준비
    # =========================================================
    def _get_or_create_worksheet(self, title: str, rows: int = 1000, cols: int = 20):
        try:
            ws = self.sh.worksheet(title)
            return ws
        except gspread.WorksheetNotFound:
            log_debug(f"[INFO] 워크시트 생성: {title}")
            return self.sh.add_worksheet(title=title, rows=rows, cols=cols)

    def _ensure_all_headers(self) -> None:
        self._ensure_header(self.raw_sheet, RAW_CHAT_HEADERS)
        self._ensure_header(self.file_dedup_sheet, FILE_DEDUP_HEADERS)
        self._ensure_header(self.negative_sheet, TREND_HEADERS)
        self._ensure_header(self.positive_sheet, TREND_HEADERS)
        self._ensure_header(self.suggestions_sheet, TREND_HEADERS)
        self._ensure_header(self.trend_sheet, TREND_HEADERS)

    def _ensure_header(self, worksheet, headers: List[str]) -> None:
        if not WRITE_HEADER_IF_EMPTY:
            return

        first_row = worksheet.row_values(1)
        if first_row:
            return

        worksheet.append_row(headers, value_input_option="RAW")
        log_debug(f"[INFO] 헤더 입력 완료: {worksheet.title}")

    # =========================================================
    # 공통 유틸
    # =========================================================
    def _worksheet_by_key(self, key: str):
        normalized = str(key).strip().lower()

        mapping = {
            "raw_chat": self.raw_sheet,
            WORKSHEET_NAME.strip().lower(): self.raw_sheet,
            "file_dedup": self.file_dedup_sheet,
            FILE_DEDUP_WORKSHEET_NAME.strip().lower(): self.file_dedup_sheet,
            "negative": self.negative_sheet,
            "negative_trend": self.negative_sheet,
            NEGATIVE_TREND_WORKSHEET_NAME.strip().lower(): self.negative_sheet,
            "positive": self.positive_sheet,
            "positive_trend": self.positive_sheet,
            POSITIVE_TREND_WORKSHEET_NAME.strip().lower(): self.positive_sheet,
            "suggestion": self.suggestions_sheet,
            "suggestions": self.suggestions_sheet,
            SUGGESTIONS_WORKSHEET_NAME.strip().lower(): self.suggestions_sheet,
            "trend": self.trend_sheet,
            "discord_trend": self.trend_sheet,
            TREND_WORKSHEET_NAME.strip().lower(): self.trend_sheet,
        }

        ws = mapping.get(normalized)
        if ws is None:
            raise ValueError(f"알 수 없는 worksheet key: {key}")
        return ws

    def _headers_by_worksheet(self, worksheet) -> List[str]:
        first_row = worksheet.row_values(1)
        if first_row:
            return first_row

        if worksheet.title == self.raw_sheet.title:
            return RAW_CHAT_HEADERS
        if worksheet.title == self.file_dedup_sheet.title:
            return FILE_DEDUP_HEADERS
        return TREND_HEADERS

    def _rows_to_values(self, rows: List[Dict[str, Any]], headers: List[str]) -> List[List[Any]]:
        values: List[List[Any]] = []
        for row in rows:
            values.append([row.get(header, "") for header in headers])
        return values

    def _append_dict_rows(self, worksheet, rows: List[Dict[str, Any]], headers: List[str]) -> None:
        if not rows:
            return

        values = self._rows_to_values(rows, headers)
        self._append_values_with_retry(worksheet, values)

    def _append_values_with_retry(self, worksheet, values: List[List[Any]], max_retries: int = 3) -> None:
        if not values:
            return

        last_error = None
        for attempt in range(1, max_retries + 1):
            try:
                worksheet.append_rows(values, value_input_option="RAW")
                return
            except Exception as e:
                last_error = e
                log_debug(
                    f"[WARN] append_rows 실패 ({worksheet.title}) "
                    f"{attempt}/{max_retries}: {e}"
                )
                time.sleep(1.0 * attempt)

        raise RuntimeError(f"{worksheet.title} 시트 append 실패: {last_error}")

    # =========================================================
    # 조회
    # =========================================================
    def get_existing_row_hashes(self) -> Set[str]:
        headers = self._headers_by_worksheet(self.raw_sheet)
        if "row_hash" not in headers:
            return set()

        col_idx = headers.index("row_hash") + 1
        values = self.raw_sheet.col_values(col_idx)

        # 첫 줄은 header
        result = {
            str(v).strip()
            for v in values[1:]
            if str(v).strip()
        }
        log_debug(f"[INFO] 기존 row_hash 조회 완료: {len(result)}건")
        return result

    def load_existing_row_hashes(self) -> Set[str]:
        return self.get_existing_row_hashes()

    def read_existing_row_hashes(self) -> Set[str]:
        return self.get_existing_row_hashes()

    def get_processed_file_keys(self) -> Set[str]:
        headers = self._headers_by_worksheet(self.file_dedup_sheet)
        if "file_key" not in headers:
            return set()

        col_idx = headers.index("file_key") + 1
        values = self.file_dedup_sheet.col_values(col_idx)

        result = {
            str(v).strip()
            for v in values[1:]
            if str(v).strip()
        }
        log_debug(f"[INFO] 기존 file_key 조회 완료: {len(result)}건")
        return result

    def load_processed_file_keys(self) -> Set[str]:
        return self.get_processed_file_keys()

    def read_processed_file_keys(self) -> Set[str]:
        return self.get_processed_file_keys()

    # =========================================================
    # raw_chat 저장
    # =========================================================
    def append_raw_chat_rows(self, rows: List[Dict[str, Any]]) -> None:
        self._append_dict_rows(self.raw_sheet, rows, RAW_CHAT_HEADERS)

    def save_raw_chat_rows(self, rows: List[Dict[str, Any]]) -> None:
        self.append_raw_chat_rows(rows)

    def add_raw_chat_rows(self, rows: List[Dict[str, Any]]) -> None:
        self.append_raw_chat_rows(rows)

    def insert_raw_chat_rows(self, rows: List[Dict[str, Any]]) -> None:
        self.append_raw_chat_rows(rows)

    # =========================================================
    # file_dedup 저장
    # =========================================================
    def append_processed_files(self, rows: List[Dict[str, Any]]) -> None:
        self._append_dict_rows(self.file_dedup_sheet, rows, FILE_DEDUP_HEADERS)

    def save_processed_files(self, rows: List[Dict[str, Any]]) -> None:
        self.append_processed_files(rows)

    def save_file_dedup_rows(self, rows: List[Dict[str, Any]]) -> None:
        self.append_processed_files(rows)

    def append_file_dedup_rows(self, rows: List[Dict[str, Any]]) -> None:
        self.append_processed_files(rows)

    # =========================================================
    # 분류 시트 저장
    # =========================================================
    def append_negative_trend_rows(self, rows: List[Dict[str, Any]]) -> None:
        self._append_dict_rows(self.negative_sheet, rows, TREND_HEADERS)

    def save_negative_trend_rows(self, rows: List[Dict[str, Any]]) -> None:
        self.append_negative_trend_rows(rows)

    def save_negative_rows(self, rows: List[Dict[str, Any]]) -> None:
        self.append_negative_trend_rows(rows)

    def append_positive_trend_rows(self, rows: List[Dict[str, Any]]) -> None:
        self._append_dict_rows(self.positive_sheet, rows, TREND_HEADERS)

    def save_positive_trend_rows(self, rows: List[Dict[str, Any]]) -> None:
        self.append_positive_trend_rows(rows)

    def save_positive_rows(self, rows: List[Dict[str, Any]]) -> None:
        self.append_positive_trend_rows(rows)

    def append_suggestion_rows(self, rows: List[Dict[str, Any]]) -> None:
        self._append_dict_rows(self.suggestions_sheet, rows, TREND_HEADERS)

    def save_suggestion_rows(self, rows: List[Dict[str, Any]]) -> None:
        self.append_suggestion_rows(rows)

    def save_suggestions_rows(self, rows: List[Dict[str, Any]]) -> None:
        self.append_suggestion_rows(rows)

    def append_trend_rows(self, rows: List[Dict[str, Any]]) -> None:
        self._append_dict_rows(self.trend_sheet, rows, TREND_HEADERS)

    def save_trend_rows(self, rows: List[Dict[str, Any]]) -> None:
        self.append_trend_rows(rows)

    def save_discord_trend_rows(self, rows: List[Dict[str, Any]]) -> None:
        self.append_trend_rows(rows)

    # =========================================================
    # generic fallback
    # =========================================================
    def save_rows_to_worksheet(self, worksheet_key: str, rows: List[Dict[str, Any]]) -> None:
        worksheet = self._worksheet_by_key(worksheet_key)
        headers = self._headers_by_worksheet(worksheet)
        self._append_dict_rows(worksheet, rows, headers)

    def append_rows_to_worksheet(self, worksheet_key: str, rows: List[Dict[str, Any]]) -> None:
        self.save_rows_to_worksheet(worksheet_key, rows)
