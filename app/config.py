import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
EXPORTS_DIR = BASE_DIR / "exports"
DB_PATH = DATA_DIR / "usage.db"

HOST = "127.0.0.1"
PORT = 8765

MAX_UPLOAD_SIZE = 50 * 1024 * 1024
