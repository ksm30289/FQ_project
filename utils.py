import hashlib
from pathlib import Path


def read_text_with_fallback(file_path: Path, encodings: list[str]) -> str:
    last_error = None
    for enc in encodings:
        try:
            return file_path.read_text(encoding=enc)
        except Exception as e:
            last_error = e
    raise RuntimeError(f"파일 인코딩을 읽을 수 없습니다: {file_path}\n{last_error}")


def make_row_hash(*values: str) -> str:
    raw = "||".join("" if v is None else str(v).strip() for v in values)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def chunk_list(data: list, size: int) -> list[list]:
    return [data[i:i + size] for i in range(0, len(data), size)]
