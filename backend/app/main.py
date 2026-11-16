"""App entry point. Run from the backend/ folder:

    .venv/Scripts/python -m uvicorn app.main:app --reload
"""
import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from .db import Base, SessionLocal, engine
from . import clock
from .routers import customers, dev, entries, incoming, messages, pay, settings, sim
from .services.scheduler import run_scheduler
from .services.shop import get_or_create_shop
from .upgrade import upgrade


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Create any missing tables at startup. Fine for a prototype; a real
    # deployment would use migrations (Alembic) so existing data is kept safely.
    Base.metadata.create_all(engine)
    upgrade(engine)  # add columns that newer slices introduced to an older dues.db
    with SessionLocal() as db:
        shop = get_or_create_shop(db)
        clock.set_offset(shop.demo_clock_offset_s)  # keep the demo clock where it was
    timer = asyncio.create_task(reminder_timer())
    yield
    timer.cancel()


def _tick() -> None:
    with SessionLocal() as db:
        run_scheduler(db, get_or_create_shop(db))


async def reminder_timer():
    """Runs the reminder timer once a minute. The database work runs in a
    worker thread so it never blocks the web server."""
    while True:
        try:
            await asyncio.to_thread(_tick)
        except Exception:  # keep the timer alive; log and try again next minute
            logging.exception("Reminder timer failed")
        await asyncio.sleep(60)


app = FastAPI(title="Credit dues assistant (concept prototype)", lifespan=lifespan)
app.include_router(settings.router)
app.include_router(entries.router)
app.include_router(customers.router)
app.include_router(messages.router)
app.include_router(pay.router)
app.include_router(incoming.router)
app.include_router(sim.router)  # simulation-only endpoints
app.include_router(dev.router)  # demo clock


@app.get("/api/health")
def health():
    return {"ok": True, "messaging": "simulated", "payments": "simulated"}
