import gspread
from google.oauth2.service_account import Credentials

from config import (
    GOOGLE_CREDENTIALS_FILE,
    SPREADSHEET_NAME,
    WORKSHEET_NAME,
    DEDUP_WORKSHEET_NAME,
    WRITE_HEADER_IF_EMPTY,
)
from utils import chunk_list

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


class GoogleSheetClient:
    def __init__(self):
        creds = Credentials.from_service_account_file(
            str(GOOGLE_CREDENTIALS_FILE),
            scopes=SCOPES,
        )
        self.gc = gspread.authorize(creds)
        self.spreadsheet = self.gc.open(SPREADSHEET_NAME)
        self.ws = self._get_or_create_worksheet(WORKSHEET_NAME, rows=2000, cols=20)
        self.dedup_ws = self._get_or_create_worksheet(DEDUP_WORKSHEET_NAME, rows=2000, cols=5)

        self._ensure_headers()

    def _get_or_create_worksheet(self, title: str, rows: int = 1000, cols: int = 20):
        try:
            return self.spreadsheet.worksheet(title)
        except gspread.WorksheetNotFound:
            return self.spreadsheet.add_worksheet(title=title, rows=str(rows), cols=str(cols))

    def _ensure_headers(self):
        if WRITE_HEADER_IF_EMPTY:
            if not self.ws.row_values(1):
                self.ws.append_row(HEADERS, value_input_option="USER_ENTERED")
            if not self.dedup_ws.row_values(1):
                self.dedup_ws.append_row(["row_hash"], value_input_option="USER_ENTERED")

    def get_existing_hashes(self) -> set[str]:
        values = self.dedup_ws.col_values(1)
        # 첫 줄은 header
        return set(values[1:]) if len(values) > 1 else set()

    def append_chat_rows(self, rows: list[dict]):
        if not rows:
            return 0

        values = []
        hash_values = []

        for row in rows:
            values.append([
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

        for chunk in chunk_list(values, 500):
            self.ws.append_rows(chunk, value_input_option="USER_ENTERED")

        for chunk in chunk_list(hash_values, 500):
            self.dedup_ws.append_rows(chunk, value_input_option="USER_ENTERED")

        return len(rows)
