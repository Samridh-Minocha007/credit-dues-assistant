"""Each test gets a fresh, empty in-memory database.

StaticPool keeps one shared connection, because an in-memory SQLite database
disappears when its connection closes."""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app import clock
from app.db import Base, get_db
from app.main import app


@pytest.fixture(autouse=True)
def no_real_gemini(monkeypatch):
    """Tests never call the real Gemini API, even if backend/.env has a key."""
    from app.config import settings

    monkeypatch.setattr(settings, "gemini_api_key", None)


@pytest.fixture
def client():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    TestSession = sessionmaker(bind=engine, expire_on_commit=False)

    def override():
        db = TestSession()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override
    clock.reset()
    yield TestClient(app)  # not used as a context manager, so the real-DB startup hook doesn't run
    app.dependency_overrides.clear()
    clock.reset()
