import gspread
from google.oauth2.service_account import Credentials

from config import (
    SPREADSHEET_ID,
    WORKSHEET_NAME,
    FILE_DEDUP_WORKSHEET_NAME,
    NEGATIVE_TREND_WORKSHEET_NAME,
    POSITIVE_TREND_WORKSHEET_NAME,
    SUGGESTIONS_WORKSHEET_NAME,
    WRITE_HEADER_IF_EMPTY,
    RAW_CHAT_HEADERS,
    TREND_HEADERS,
    ROW_DEDUP_ENABLED,
    get_google_credentials_dict,
)

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]


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
        self.suggestion_sheet = self._get_or_create_worksheet(SUGGESTIONS_WORKSHEET_NAME)

        # 선택 확장용: trend 시트가 config에 있으면 생성, 없으면 None
        self.trend_sheet = None
        try:
            from config import TREND_WORKSHEET_NAME
            self.trend_sheet = self._get_or_create_worksheet(TREND_WORKSHEET_NAME)
        except Exception:
            self.trend_sheet = None

        self._ensure_raw_sheet_header()
        self._ensure_file_dedup_header()
        self._ensure_trend_sheet_header(self.negative_sheet)
        self._ensure_trend_sheet_header(self.positive_sheet)
        self._ensure_trend_sheet_header(self.suggestion_sheet)

        if self.trend_sheet is not None:
            self._ensure_trend_sheet_header(self.trend_sheet)

    def _get_or_create_worksheet(self, title: str, rows: int = 1000, cols: int = 20):
        try:
            return self.sh.worksheet(title)
        except gspread.WorksheetNotFound:
            return self.sh.add_worksheet(title=title, rows=rows, cols=cols)

    def _ensure_header(self, worksheet, headers):
        if not WRITE_HEADER_IF_EMPTY:
            return

        values = worksheet.get_all_values()
        if not values:
            worksheet.append_row(headers, value_input_option="USER_ENTERED")
            return

        first_row = values[0]
        if not first_row:
            worksheet.update("A1", [headers])

    def _ensure_raw_sheet_header(self):
        self._ensure_header(self.raw_sheet, RAW_CHAT_HEADERS)

    def _ensure_file_dedup_header(self):
        self._ensure_header(self.file_dedup_sheet, ["file_key", "file_name"])

    def _ensure_trend_sheet_header(self, worksheet):
        self._ensure_header(worksheet, TREND_HEADERS)

    def get_existing_row_hashes(self):
        if not ROW_DEDUP_ENABLED:
            return set()

        values = self.raw_sheet.get_all_values()
        if len(values) <= 1:
            return set()

        header = values[0]
        try:
            row_hash_idx = header.index("row_hash")
        except ValueError:
            return set()

        result = set()
        for row in values[1:]:
            if len(row) > row_hash_idx and str(row[row_hash_idx]).strip():
                result.add(str(row[row_hash_idx]).strip())
        return result

    def get_processed_file_keys(self):
        values = self.file_dedup_sheet.get_all_values()
        if len(values) <= 1:
            return set()

        header = values[0]
        file_key_idx = 0
        try:
            file_key_idx = header.index("file_key")
        except ValueError:
            file_key_idx = 0

        result = set()
        for row in values[1:]:
            if len(row) > file_key_idx and str(row[file_key_idx]).strip():
                result.add(str(row[file_key_idx]).strip())
        return result

    def mark_file_processed(self, file_key: str, file_name: str):
        self.file_dedup_sheet.append_row(
            [file_key, file_name],
            value_input_option="USER_ENTERED",
        )

    def append_processed_file_keys(self, rows):
        """
        rows 예시:
        [
            [file_key, file_name],
            [file_key, file_name],
        ]
        """
        if not rows:
            return
        self.file_dedup_sheet.append_rows(rows, value_input_option="USER_ENTERED")

    def append_raw_rows(self, rows):
        """
        rows가 dict 리스트여도 되고, 이미 정규화된 list 리스트여도 되게 처리.
        dict 예시:
        {
            "datetime": "...",
            "user": "...",
            "message": "...",
            "row_hash": "...",
            "source_file": "..."
        }

        또는
        {
            "date": "...",
            "time": "...",
            "user": "...",
            "message": "...",
            "source_file_name": "...",
            "row_hash": "..."
        }
        """
        if not rows:
            return

        normalized_rows = []

        for row in rows:
            if isinstance(row, dict):
                # 기존 포맷(datetime 기반)
                if "datetime" in row:
                    normalized_rows.append([
                        row.get("datetime", ""),
                        row.get("user", ""),
                        row.get("message", ""),
                        row.get("row_hash", ""),
                        row.get("source_file", ""),
                    ])
                else:
                    # 확장 포맷(date/time 분리 기반)
                    normalized_rows.append([
                        row.get("date", ""),
                        row.get("time", ""),
                        row.get("user", ""),
                        row.get("message", ""),
                        row.get("source_file_name", ""),
                        row.get("row_hash", ""),
                    ])
            else:
                # 이미 list 형태면 그대로 사용
                normalized_rows.append(row)

        self.raw_sheet.append_rows(normalized_rows, value_input_option="USER_ENTERED")

    def append_negative_rows(self, rows):
        if rows:
            self.negative_sheet.append_rows(rows, value_input_option="USER_ENTERED")

    def append_positive_rows(self, rows):
        if rows:
            self.positive_sheet.append_rows(rows, value_input_option="USER_ENTERED")

    def append_suggestion_rows(self, rows):
        if rows:
            self.suggestion_sheet.append_rows(rows, value_input_option="USER_ENTERED")

    def append_trend_rows(self, rows):
        if not rows:
            return

        if self.trend_sheet is None:
            raise RuntimeError(
                "TREND_WORKSHEET_NAME 이 config.py에 정의되지 않았습니다. "
                "디스코드 동향 시트를 쓰려면 config에 TREND_WORKSHEET_NAME을 추가하세요."
            )

        self.trend_sheet.append_rows(rows, value_input_option="USER_ENTERED")

    def append_classified_rows(self, sheet_name: str, rows):
        """
        sheet_name 기준으로 적절한 시트에 append.
        main.py에서 공통 라우팅할 때 사용.
        """
        if not rows:
            return

        name_map = {
            NEGATIVE_TREND_WORKSHEET_NAME: self.negative_sheet,
            POSITIVE_TREND_WORKSHEET_NAME: self.positive_sheet,
            SUGGESTIONS_WORKSHEET_NAME: self.suggestion_sheet,
        }

        if self.trend_sheet is not None:
            try:
                from config import TREND_WORKSHEET_NAME
                name_map[TREND_WORKSHEET_NAME] = self.trend_sheet
            except Exception:
                pass

        if sheet_name not in name_map:
            raise ValueError(f"알 수 없는 시트명: {sheet_name}")

        name_map[sheet_name].append_rows(rows, value_input_option="USER_ENTERED")
