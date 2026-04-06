# sheets.py
import gspread
from google.oauth2.service_account import Credentials

from config import get_google_credentials_dict, SPREADSHEET_ID

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

        # 이 호출 자체도 read 1회이므로, 앱 재시작/재실행 빈도를 낮추는 게 중요
        self.spreadsheet = gc.open_by_key(SPREADSHEET_ID)

    def get_or_create_worksheet(self, title: str, rows: int = 1000, cols: int = 20):
        try:
            return self.spreadsheet.worksheet(title)
        except gspread.WorksheetNotFound:
            return self.spreadsheet.add_worksheet(title=title, rows=rows, cols=cols)

    def ensure_sheet(self, sheet_name: str, headers: list[str]):
        """
        읽기 최소화 버전:
        - 시트 존재 여부만 확인
        - 있으면 헤더 검사 안 함
        - 없을 때만 생성 후 헤더 1회 입력
        """
        try:
            self.spreadsheet.worksheet(sheet_name)
        except gspread.WorksheetNotFound:
            ws = self.spreadsheet.add_worksheet(
                title=sheet_name,
                rows=1000,
                cols=max(len(headers), 10),
            )
            ws.append_row(headers, value_input_option="USER_ENTERED")

    def append_rows(self, sheet_name: str, rows: list[list]):
        if not rows:
            return

        ws = self.get_or_create_worksheet(sheet_name)
        ws.append_rows(rows, value_input_option="USER_ENTERED")

    def get_existing_row_hashes(self, sheet_name: str = RAW_CHAT_SHEET) -> set[str]:
        """
        raw_chat의 row_hash를 읽어서 중복 업로드 방지.
        주의: 이 함수는 전체 시트를 읽으므로 read quota를 사용한다.
        """
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
            if len(row) > hash_idx:
                row_hash = row[hash_idx].strip()
                if row_hash:
                    result.add(row_hash)

        return result

    def get_processed_file_keys(self, sheet_name: str = PROCESSED_FILES_SHEET) -> set[str]:
        """
        이미 처리한 파일 키 목록을 읽어 중복 파일 처리 방지.
        주의: 이 함수도 read quota를 사용한다.
        """
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

    def append_processed_file_keys(
        self,
        file_keys: list[str],
        sheet_name: str = PROCESSED_FILES_SHEET,
    ):
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
