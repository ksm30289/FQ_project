import gspread
from google.oauth2.service_account import Credentials
from config import SPREADSHEET_ID

from config import (
    DEDUP_WORKSHEET_NAME,
    FILE_DEDUP_MODE,
    FILE_DEDUP_WORKSHEET_NAME,
    SPREADSHEET_NAME,
    WORKSHEET_NAME,
    WRITE_HEADER_IF_EMPTY,
    get_google_credentials_dict,
)
from utils import chunked

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

HEADERS = [
    "room_name",
    "source_file",
    "datetime",
    "date",
    "time",
    "user_name",
    "message",
    "row_hash",
]

FILE_HEADERS = [
    "file_key",
    "file_id",
    "file_name",
    "file_size",
]


class GoogleSheetClient:
    def __init__(self):
        creds = Credentials.from_service_account_info(
            get_google_credentials_dict(),
            scopes=SCOPES,
        )
        self.gc = gspread.authorize(creds)
        self.spreadsheet = self.gc.open_by_key(SPREADSHEET_ID)

        self.ws = self._get_or_create_worksheet(WORKSHEET_NAME, rows=2000, cols=20)
        self.dedup_ws = self._get_or_create_worksheet(DEDUP_WORKSHEET_NAME, rows=2000, cols=5)
        self.file_ws = self._get_or_create_worksheet(FILE_DEDUP_WORKSHEET_NAME, rows=1000, cols=5)

        self._ensure_headers()

    def _get_or_create_worksheet(self, title: str, rows: int, cols: int):
        try:
            return self.spreadsheet.worksheet(title)
        except gspread.WorksheetNotFound:
            return self.spreadsheet.add_worksheet(title=title, rows=str(rows), cols=str(cols))

    def _ensure_headers(self):
        if not WRITE_HEADER_IF_EMPTY:
            return

        if not self.ws.row_values(1):
            self.ws.append_row(HEADERS, value_input_option="USER_ENTERED")

        if not self.dedup_ws.row_values(1):
            self.dedup_ws.append_row(["row_hash"], value_input_option="USER_ENTERED")

        if not self.file_ws.row_values(1):
            self.file_ws.append_row(FILE_HEADERS, value_input_option="USER_ENTERED")

    def get_existing_row_hashes(self) -> set[str]:
        values = self.dedup_ws.col_values(1)
        return set(values[1:]) if len(values) > 1 else set()

    def get_processed_file_keys(self) -> set[str]:
        values = self.file_ws.col_values(1)
        return set(values[1:]) if len(values) > 1 else set()

    def append_chat_rows(self, rows: list[dict]) -> int:
        if not rows:
            return 0

        chat_values = []
        hash_values = []

        for row in rows:
            chat_values.append([
                row["room_name"],
                row["source_file"],
                row["datetime"],
                row["date"],
                row["time"],
                row["user_name"],
                row["message"],
                row["row_hash"],
            ])
            hash_values.append([row["row_hash"]])

        for chunk in chunked(chat_values, 500):
            self.ws.append_rows(chunk, value_input_option="USER_ENTERED")

        for chunk in chunked(hash_values, 500):
            self.dedup_ws.append_rows(chunk, value_input_option="USER_ENTERED")

        return len(rows)

    def mark_file_processed(self, file_key: str, file_id: str, file_name: str, file_size: str):
        self.file_ws.append_row(
            [file_key, file_id, file_name, file_size],
            value_input_option="USER_ENTERED",
        )
