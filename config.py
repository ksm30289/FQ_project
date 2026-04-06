from pathlib import Path

# ===== 기본 설정 =====
BASE_DIR = Path(__file__).resolve().parent
UPLOAD_DIR = BASE_DIR / "uploads"

# 구글 서비스 계정 키 파일
GOOGLE_CREDENTIALS_FILE = BASE_DIR / "credentials.json"

# 구글 시트 정보
SPREADSHEET_NAME = "Kakao Open Chat Archive"
WORKSHEET_NAME = "raw_chat"

# 대상 채팅방 이름(없으면 파일명 기준 사용 가능)
DEFAULT_ROOM_NAME = "특정 게임 오픈톡방"

# 첫 실행 시 헤더 생성 여부
WRITE_HEADER_IF_EMPTY = True

# 중복 방지용 시트 이름
DEDUP_WORKSHEET_NAME = "_dedupe_keys"

# 지원 인코딩 후보
ENCODINGS = ["utf-8-sig", "utf-8", "cp949", "euc-kr"]

# 카카오 내보내기 형식 예시를 가정한 정규식 처리 옵션
# 필요한 경우 parser.py에서 추가 수정
