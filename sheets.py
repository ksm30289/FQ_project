import gspread
from google.oauth2.service_account import Credentials

from config import (
    SPREADSHEET_ID,
    WORKSHEET_NAME,
    FILE_DEDUP_WORKSHEET_NAME,
    WRITE_HEADER_IF_EMPTY,
    RAW_CHAT_HEADERS,
    ROW_DEDUP_ENABLED,
    get_google_credentials_dict,
)
from utils import make_row_hash

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

        self._ensure_raw_sheet_header()
        self._ensure_file_dedup_header()

    def _get_or_create_worksheet(self, title: str, rows: int = 1000, cols: int = 20):
        try:
            return self.sh.worksheet(title)
        except gspread.WorksheetNotFound:
            return self.sh.add_worksheet(title=title, rows=rows, cols=cols)

    def _ensure_raw_sheet_header(self):
        if not WRITE_HEADER_IF_EMPTY:
            return

        values = self.raw_sheet.get_all_values()
        if not values:
            self.raw_sheet.append_row(RAW_CHAT_HEADERS, value_input_option="USER_ENTERED")
            return

        first_row = values[0] if values else []
        if not first_row:
            self.raw_sheet.update("A1:D1", [RAW_CHAT_HEADERS])

    def _ensure_file_dedup_header(self):
        if not WRITE_HEADER_IF_EMPTY:
            return

        values = self.file_dedup_sheet.get_all_values()
        if not values:
            self.file_dedup_sheet.append_row(["file_key"], value_input_option="USER_ENTERED")
            return

        first_row = values[0] if values else []
        if not first_row:
            self.file_dedup_sheet.update("A1:A1", [["file_key"]])

    def get_existing_row_hashes(self) -> set:
        """
        raw_chat의 row_hash 컬럼을 set으로 로드
        """
        if not ROW_DEDUP_ENABLED:
            return set()

        values = self.raw_sheet.get_all_values()
        if not values or len(values) <= 1:
            return set()

        header = values[0]
        try:
            hash_idx = header.index("row_hash")
        except ValueError:
            return set()

        result = set()
        for row in values[1:]:
            if len(row) > hash_idx and row[hash_idx]:
                result.add(row[hash_idx])

        return result

    def get_processed_file_keys(self) -> set:
        values = self.file_dedup_sheet.get_all_values()
        if not values or len(values) <= 1:
            return set()

        header = values[0]
        try:
            idx = header.index("file_key")
        except ValueError:
            return set()

        result = set()
        for row in values[1:]:
            if len(row) > idx and row[idx]:
                result.add(row[idx])

        return result

    def append_raw_rows_batch(self, rows: list):
        """
        rows 형식:
        [
            [datetime, user, message, row_hash],
            ...
        ]
        """
        if not rows:
            return

        self.raw_sheet.append_rows(
            rows,
            value_input_option="USER_ENTERED",
        )

    def append_processed_file_key(self, file_key: str):
        if not file_key:
            return

        self.file_dedup_sheet.append_row(
            [file_key],
            value_input_option="USER_ENTERED",
        )

    def build_raw_rows_for_upload(self, parsed_rows: list, existing_hashes: set):
        """
        parsed_rows:
        [
            {"datetime": "...", "user": "...", "message": "..."}
        ]
        """
        upload_rows = []

        for r in parsed_rows:
            row_hash = make_row_hash(r["datetime"], r["user"], r["message"])

            if ROW_DEDUP_ENABLED and row_hash in existing_hashes:
                continue

            upload_rows.append([
                r["datetime"],
                r["user"],
                r["message"],
                row_hash,
            ])

            if ROW_DEDUP_ENABLED:
                existing_hashes.add(row_hash)

        return upload_rows
