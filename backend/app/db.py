"""Database connection.

SQLite is a single file on disk, so there is no database server to install.
`check_same_thread=False` is needed because FastAPI runs normal (non-async)
endpoints on a pool of worker threads, and SQLite by default refuses to be
used from a thread other than the one that opened it.
"""
from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from .config import settings

engine = create_engine(settings.database_url, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


def get_db():
    """One database session per HTTP request, always closed afterwards."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
