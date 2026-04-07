from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload
from google.oauth2.service_account import Credentials

import io

from config import (
    DRIVE_SOURCE_FOLDER_ID,
    DRIVE_PROCESSED_FOLDER_ID,
    ALLOWED_EXTENSIONS,
    MOVE_PROCESSED_FILE,
    get_google_credentials_dict,
)

SCOPES = [
    "https://www.googleapis.com/auth/drive",
]


class GoogleDriveClient:
    def __init__(self):
        creds_info = get_google_credentials_dict()
        creds = Credentials.from_service_account_info(creds_info, scopes=SCOPES)

        self.service = build("drive", "v3", credentials=creds)

    def list_txt_files(self, limit=10):
        """
        Drive에서 txt 파일 목록 조회
        """
        query = (
            f"'{DRIVE_SOURCE_FOLDER_ID}' in parents "
            f"and trashed = false"
        )

        results = self.service.files().list(
            q=query,
            pageSize=limit,
            fields="files(id, name, size, modifiedTime)",
            orderBy="createdTime desc",
        ).execute()

        files = results.get("files", [])

        # 확장자 필터링 (여기서 미리 걸러서 속도 개선)
        filtered = [
            f for f in files
            if any(f["name"].lower().endswith(ext) for ext in ALLOWED_EXTENSIONS)
        ]

        return filtered

    def download_txt_file(self, file_id: str) -> str:
        """
        txt 파일 다운로드
        """
        request = self.service.files().get_media(fileId=file_id)

        fh = io.BytesIO()
        downloader = MediaIoBaseDownload(fh, request)

        done = False
        while not done:
            _, done = downloader.next_chunk()

        fh.seek(0)
        return fh.read().decode("utf-8", errors="ignore")

    def move_file_to_processed(self, file_id: str):
        """
        처리 완료 파일을 processed 폴더로 이동
        """
        if not MOVE_PROCESSED_FILE or not DRIVE_PROCESSED_FOLDER_ID:
            return

        try:
            # 기존 부모 폴더 조회
            file = self.service.files().get(
                fileId=file_id,
                fields="parents"
            ).execute()

            previous_parents = ",".join(file.get("parents", []))

            # 폴더 이동
            self.service.files().update(
                fileId=file_id,
                addParents=DRIVE_PROCESSED_FOLDER_ID,
                removeParents=previous_parents,
                fields="id, parents"
            ).execute()

            print(f"[INFO] 파일 이동 완료: {file_id}")

        except Exception as e:
            print(f"[ERROR] 파일 이동 실패: {file_id} | {e}")
