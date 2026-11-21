"""Reads settings from environment variables (or a local, git-ignored .env file).

Keeping secrets like GEMINI_API_KEY out of the code means the repo can be
public without leaking anything.
"""
import os
from pathlib import Path

from dotenv import load_dotenv

BACKEND_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BACKEND_DIR / ".env")  # loads backend/.env if it exists; does nothing otherwise


class Settings:
    # Default: backend/dues.db, wherever the server is started from.
    database_url: str = os.getenv("DATABASE_URL", f"sqlite:///{(BACKEND_DIR / 'dues.db').as_posix()}")
    gemini_api_key: str | None = os.getenv("GEMINI_API_KEY") or None
    gemini_model: str = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
    # Where the simulated payment page lives (the React app). Used to build links.
    public_base_url: str = os.getenv("PUBLIC_BASE_URL", "http://localhost:5173").rstrip("/")


settings = Settings()
