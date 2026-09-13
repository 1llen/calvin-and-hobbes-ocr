from pathlib import Path

NEWS_ID = 10995

# chapter_id and page counts taken from the batcave.biz reader links/page-selector
ISSUES = [
    {"number": 1, "chapter_id": 72371, "pages": 163},
    {"number": 2, "chapter_id": 72372, "pages": 166},
    {"number": 3, "chapter_id": 72373, "pages": 164},
    {"number": 4, "chapter_id": 72374, "pages": 167},
    {"number": 5, "chapter_id": 72375, "pages": 172},
    {"number": 6, "chapter_id": 72376, "pages": 173},
    {"number": 7, "chapter_id": 72377, "pages": 172},
    {"number": 8, "chapter_id": 72378, "pages": 176},
    {"number": 9, "chapter_id": 72379, "pages": 175},
    {"number": 10, "chapter_id": 72380, "pages": 176},
    {"number": 11, "chapter_id": 72381, "pages": 166},
]

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
IMAGES_DIR = DATA_DIR / "images"
DB_PATH = DATA_DIR / "ocr.sqlite3"
BROWSER_PROFILE_DIR = DATA_DIR / "browser_profile"
