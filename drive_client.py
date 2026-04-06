from io import BytesIO
from typing import Dict, List

from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload

from config import (
    ALLOWED_EXTENSIONS,
    DRIVE_PROCESSED_FOLDER_ID,
    DRIVE_SOURCE_FOLDER_ID,
    get_google_credentials_dict,
)

SCOPES = [
    "https://www.googleapis.com/auth/drive",
    "https://www.googleapis.com/auth/spreadsheets",
]


class GoogleDriveClient:
    def __init__(self):
        creds = Credentials.from_service_account_info(
            get_google_credentials_dict(),
            scopes=SCOPES,
        )
        self.service = build("drive", "v3", credentials=creds, cache_discovery=False)

    def list_txt_files(self, limit: int = 20) -> List[Dict]:
        ext_conditions = " or ".join([f"name contains '{ext}'" for ext in ALLOWED_EXTENSIONS])
        query = (
            f"'{DRIVE_SOURCE_FOLDER_ID}' in parents "
            f"and trashed = false "
            f"and ({ext_conditions})"
        )

        resp = self.service.files().list(
            q=query,
            fields="files(id, name, size, createdTime, modifiedTime, mimeType, parents)",
            orderBy="createdTime asc",
            pageSize=limit,
            supportsAllDrives=True,
            includeItemsFromAllDrives=True,
        ).execute()

        return resp.get("files", [])

    def download_text_file(self, file_id: str) -> str:
        request = self.service.files().get_media(fileId=file_id)
        fh = BytesIO()
        downloader = MediaIoBaseDownload(fh, request)

        done = False
        while not done:
            _, done = downloader.next_chunk()

        content = fh.getvalue()

        for enc in ("utf-8-sig", "utf-8", "cp949", "euc-kr"):
            try:
                return content.decode(enc)
            except UnicodeDecodeError:
                continue

        raise RuntimeError(f"파일 디코딩 실패: {file_id}")

    def move_to_processed(self, file_id: str):
        if not DRIVE_PROCESSED_FOLDER_ID:
            return

        meta = self.service.files().get(
            fileId=file_id,
            fields="id, parents",
            supportsAllDrives=True,
        ).execute()

        previous_parents = ",".join(meta.get("parents", []))

        self.service.files().update(
            fileId=file_id,
            addParents=DRIVE_PROCESSED_FOLDER_ID,
            removeParents=previous_parents,
            fields="id, parents",
            supportsAllDrives=True,
        ).execute()
