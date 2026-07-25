from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

DOWNLOAD_DIR = BASE_DIR / "downloads"
DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)

FINVIZ_URL = "https://elite.finviz.com/screener"

TIMEOUT = 10000