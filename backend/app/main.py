"""App entry point. Run from the backend/ folder:

    .venv/Scripts/python -m uvicorn app.main:app --reload
"""
from contextlib import asynccontextmanager

from fastapi import FastAPI

from .db import Base, SessionLocal, engine
from .routers import customers, entries, settings
from .services.shop import get_or_create_shop


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Create any missing tables at startup. Fine for a prototype; a real
    # deployment would use migrations (Alembic) so existing data is kept safely.
    Base.metadata.create_all(engine)
    with SessionLocal() as db:
        get_or_create_shop(db)
    yield


app = FastAPI(title="Credit dues assistant (concept prototype)", lifespan=lifespan)
app.include_router(settings.router)
app.include_router(entries.router)
app.include_router(customers.router)


@app.get("/api/health")
def health():
    return {"ok": True, "messaging": "simulated", "payments": "simulated"}
