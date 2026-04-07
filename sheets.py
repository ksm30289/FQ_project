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

        self._ensure_raw_sheet_header()
        self._ensure_file_dedup_header()
        self._ensure_trend_sheet_header(self.negative_sheet)
        self._ensure_trend_sheet_header(self.positive_sheet)
        self._ensure_trend_sheet_header(self.suggestion_sheet)

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
            if len(row) > row_hash_idx and row[row_hash_idx].strip():
                result.add(row[row_hash_idx].strip())
        return result

    def get_processed_file_keys(self):
        values = self.file_dedup_sheet.get_all_values()
        if len(values) <= 1:
            return set()

        result = set()
        for row in values[1:]:
            if row and row[0].strip():
                result.add(row[0].strip())
        return result

    def mark_file_processed(self, file_key: str, file_name: str):
        self.file_dedup_sheet.append_row(
            [file_key, file_name],
            value_input_option="USER_ENTERED",
        )

    def append_raw_rows(self, rows):
        if not rows:
            return

        normalized_rows = []
        for row in rows:
            normalized_rows.append([
                row.get("datetime", ""),
                row.get("user", ""),
                row.get("message", ""),
                row.get("row_hash", ""),
                row.get("source_file", ""),
            ])

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
