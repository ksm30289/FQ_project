# sheets.py
import gspread
from google.oauth2.service_account import Credentials

from config import (
    get_google_credentials_dict,
    SPREADSHEET_ID,
)
from trend_classifier import make_trend_key_from_row_values


RAW_CHAT_SHEET = "raw_chat"
PROCESSED_FILES_SHEET = "_processed_files"

RAW_HEADERS = [
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
        creds_dict = get_google_credentials_dict()

        scopes = [
            "https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/drive",
        ]

        creds = Credentials.from_service_account_info(creds_dict, scopes=scopes)
        gc = gspread.authorize(creds)

        self.spreadsheet = gc.open_by_key(SPREADSHEET_ID)

    def get_or_create_worksheet(self, title: str, rows: int = 1000, cols: int = 20):
        try:
            return self.spreadsheet.worksheet(title)
        except gspread.WorksheetNotFound:
            return self.spreadsheet.add_worksheet(title=title, rows=rows, cols=cols)

    def ensure_sheet(self, sheet_name: str, headers: list[str]):
        ws = self.get_or_create_worksheet(sheet_name, rows=1000, cols=max(len(headers), 10))
        existing_header = ws.row_values(1)

        if existing_header != headers:
            ws.clear()
            ws.append_row(headers, value_input_option="USER_ENTERED")

    def append_rows(self, sheet_name: str, rows: list[list]):
        if not rows:
            return

        ws = self.get_or_create_worksheet(sheet_name)
        ws.append_rows(rows, value_input_option="USER_ENTERED")

    # =========================
    # raw_chat 중복 방지
    # =========================
    def get_existing_row_hashes(self, sheet_name: str = RAW_CHAT_SHEET) -> set[str]:
        ws = self.get_or_create_worksheet(sheet_name)
        values = ws.get_all_values()

        if not values or len(values) < 2:
            return set()

        header = values[0]
        if "row_hash" not in header:
            return set()

        hash_idx = header.index("row_hash")
        result = set()

        for row in values[1:]:
            if len(row) > hash_idx and row[hash_idx].strip():
                result.add(row[hash_idx].strip())

        return result

    # =========================
    # 파일 중복 방지
    # =========================
    def get_processed_file_keys(self, sheet_name: str = PROCESSED_FILES_SHEET) -> set[str]:
        ws = self.get_or_create_worksheet(sheet_name)
        values = ws.get_all_values()

        if not values:
            return set()

        if values[0] and values[0][0] == "file_key":
            data_rows = values[1:]
        else:
            data_rows = values

        result = set()
        for row in data_rows:
            if row and row[0].strip():
                result.add(row[0].strip())

        return result

    def append_processed_file_keys(self, file_keys: list[str], sheet_name: str = PROCESSED_FILES_SHEET):
        if not file_keys:
            return

        ws = self.get_or_create_worksheet(sheet_name)
        values = ws.get_all_values()

        if not values:
            ws.append_row(["file_key"], value_input_option="USER_ENTERED")
        elif values[0] and values[0][0] != "file_key":
            ws.insert_row(["file_key"], 1)

        rows = [[key] for key in file_keys]
        ws.append_rows(rows, value_input_option="USER_ENTERED")

    # =========================
    # 트렌드 중복 방지
    # =========================
    def get_existing_trend_keys(self, sheet_name: str) -> set[str]:
        ws = self.get_or_create_worksheet(sheet_name)
        values = ws.get_all_values()

        if not values or len(values) < 2:
            return set()

        result = set()
        for row in values[1:]:
            date = row[0] if len(row) > 0 else ""
            time = row[1] if len(row) > 1 else ""
            user_name = row[2] if len(row) > 2 else ""
            message = row[3] if len(row) > 3 else ""

            if date or time or user_name or message:
                key = make_trend_key_from_row_values(
                    date, time, user_name, message, sheet_name
                )
                result.add(key)

        return result
