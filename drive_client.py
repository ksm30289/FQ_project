import io
import os
import time
from typing import List, Dict, Optional

from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaIoBaseDownload

from config import get_google_credentials_dict


SCOPES = [
    "https://www.googleapis.com/auth/drive.readonly",
]


def _get_env(name: str, default: str = "") -> str:
    value = os.getenv(name)
    if value is None:
        return default
    return str(value).strip()


def _get_int_env(name: str, default: int) -> int:
    value = os.getenv(name)
    if value is None or str(value).strip() == "":
        return default
    try:
        return int(str(value).strip())
    except Exception:
        return default


def _get_bool_env(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return str(value).strip().lower() in ("1", "true", "yes", "y", "on")


DRIVE_FOLDER_ID = _get_env("DRIVE_FOLDER_ID")
MAX_FILES_PER_RUN = _get_int_env("MAX_FILES_PER_RUN", 100)
DEBUG_LOG = _get_bool_env("DEBUG_LOG", True)

MAX_RETRIES = 3
RETRY_SLEEP = 1.2

GOOGLE_DOC_MIME = "application/vnd.google-apps.document"


def log(msg: str) -> None:
    if DEBUG_LOG:
        print(msg)


class GoogleDriveClient:
    def __init__(self):
        creds_info = get_google_credentials_dict()
        creds = Credentials.from_service_account_info(creds_info, scopes=SCOPES)

        self.service = build(
            "drive",
            "v3",
            credentials=creds,
            cache_discovery=False,
        )

    def list_txt_files(self, limit: Optional[int] = None) -> List[Dict]:
        if limit is None:
            limit = MAX_FILES_PER_RUN

        query_parts = [
            "trashed = false",
            "("
            "mimeType = 'text/plain' "
            f"or mimeType = '{GOOGLE_DOC_MIME}'"
            ")",
        ]

        if DRIVE_FOLDER_ID:
            query_parts.append(f"'{DRIVE_FOLDER_ID}' in parents")

        query = " and ".join(query_parts)
        log(f"[Drive Query] {query}")

        files: List[Dict] = []
        page_token = None

        while True:
            request = self.service.files().list(
                q=query,
                pageSize=min(100, max(1, limit - len(files))),
                pageToken=page_token,
                fields="nextPageToken, files(id, name, mimeType, modifiedTime, size)",
                orderBy="modifiedTime desc",
                supportsAllDrives=True,
                includeItemsFromAllDrives=True,
            )

            response = self._execute_with_retry(request)
            batch = response.get("files", [])
            files.extend(batch)

            log(f"[Drive] fetched={len(batch)} total={len(files)}")

            if len(files) >= limit:
                break

            page_token = response.get("nextPageToken")
            if not page_token:
                break

        return files[:limit]

    def get_file_metadata(self, file_id: str) -> Dict:
        request = self.service.files().get(
            fileId=file_id,
            fields="id, name, mimeType, size",
            supportsAllDrives=True,
        )
        return self._execute_with_retry(request)

    def _download_request_bytes(self, request) -> bytes:
        fh = io.BytesIO()
        downloader = MediaIoBaseDownload(fh, request)

        done = False
        while not done:
            _, done = downloader.next_chunk()

        return fh.getvalue()

    def download_txt_file(self, file_id: str, mime_type: Optional[str] = None) -> str:
        meta = self.get_file_metadata(file_id)

        actual_name = str(meta.get("name", "")).strip()
        actual_mime = str(meta.get("mimeType", "")).strip()
        actual_size = str(meta.get("size", "")).strip()

        if not mime_type:
            mime_type = actual_mime

        log(
            f"[Drive] download start "
            f"id={file_id} name={actual_name} mime={mime_type} size={actual_size or 'unknown'}"
        )

        if mime_type == GOOGLE_DOC_MIME:
            request = self.service.files().export_media(
                fileId=file_id,
                mimeType="text/plain",
            )
        else:
            request = self.service.files().get_media(fileId=file_id)

        raw_bytes = self._download_request_bytes(request)
        log(f"[Drive] downloaded bytes={len(raw_bytes)}")

        if not raw_bytes:
            log("[Drive] downloaded content is empty")
            return ""

        for encoding in ("utf-8-sig", "utf-8", "cp949", "euc-kr", "utf-16"):
            try:
                text = raw_bytes.decode(encoding)
                log(f"[Drive] decode success encoding={encoding} text_len={len(text)}")
                preview = repr(text[:120])
                log(f"[Drive] preview={preview}")
                return text
            except UnicodeDecodeError:
                continue

        text = raw_bytes.decode("utf-8", errors="replace")
        log(f"[Drive] decode fallback utf-8-replace text_len={len(text)}")
        preview = repr(text[:120])
        log(f"[Drive] preview={preview}")
        return text

    def read_text_file(self, file_id: str, mime_type: Optional[str] = None) -> str:
        return self.download_txt_file(file_id, mime_type)

    def download_text_file(self, file_id: str, mime_type: Optional[str] = None) -> str:
        return self.download_txt_file(file_id, mime_type)

    def _execute_with_retry(self, request):
        last_error = None

        for attempt in range(1, MAX_RETRIES + 1):
            try:
                return request.execute()
            except HttpError as e:
                last_error = e
                if attempt < MAX_RETRIES:
                    sleep = RETRY_SLEEP * attempt
                    log(f"[Retry] {attempt} sleep={sleep}s")
                    time.sleep(sleep)
                else:
                    raise

        raise RuntimeError(f"Drive API 실패: {last_error}")
