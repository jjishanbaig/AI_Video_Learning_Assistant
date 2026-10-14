from pathlib import Path
import os
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parents[1]
load_dotenv(BASE_DIR / ".env")
DATA_DIR = BASE_DIR / "data"
UPLOAD_DIR = DATA_DIR / "uploads"
EXPORT_DIR = DATA_DIR / "exports"
for folder in (DATA_DIR, UPLOAD_DIR, EXPORT_DIR):
    folder.mkdir(parents=True, exist_ok=True)

DATABASE_URL = f"sqlite:///{(DATA_DIR / 'learning_assistant.db').as_posix()}"
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "").strip()
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.8-flash").strip()
MAX_UPLOAD_MB = int(os.getenv("MAX_UPLOAD_MB", "250"))
FRONTEND_ORIGIN = os.getenv("FRONTEND_ORIGIN", "http://localhost:5173")
