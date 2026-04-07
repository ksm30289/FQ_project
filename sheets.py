import os
import json
import gspread
from google.oauth2.service_account import Credentials

from utils import make_row_hash

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]


class GoogleSheetClient:
    def __init__(self):
        creds_info = json.loads(os.environ["GOOGLE_CREDENTIALS"])
        creds = Credentials.from_service_account_info(creds_info, scopes=SCOPES)
        self.gc = gspread.authorize(creds)

        self.spreadsheet_id = os.environ["SPREADSHEET_ID"]
        self.sh = self.gc.open_by_key(self.spreadsheet_id)

        self.raw_sheet = self.sh.worksheet("raw_chat")
        self.meta_sheet = self.sh.worksheet("_meta")

    def get_existing_row_hashes(self) -> set:
        """
        raw_chat의 마지막 열(row_hash)만 가져와서 set으로 만듦
        전체 행을 다 가져오는 것보다 훨씬 빠름
        """
        values = self.raw_sheet.get_all_values()
        if not values or len(values) <= 1:
            return set()

        header = values[0]
        try:
            hash_idx = header.index("row_hash")
        except ValueError:
            # row_hash 컬럼이 아직 없으면 전체 비어있다고 간주
            return set()

        result = set()
        for row in values[1:]:
            if len(row) > hash_idx and row[hash_idx]:
                result.add(row[hash_idx])
        return result

    def get_processed_file_keys(self) -> set:
        values = self.meta_sheet.get_all_values()
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
        self.meta_sheet.append_row([file_key], value_input_option="USER_ENTERED")

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
            if row_hash in existing_hashes:
                continue

            upload_rows.append([
                r["datetime"],
                r["user"],
                r["message"],
                row_hash,
            ])
            existing_hashes.add(row_hash)

        return upload_rows
