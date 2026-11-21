"""App entry point. Run from the backend/ folder:

    .venv/Scripts/python -m uvicorn app.main:app --reload
"""
import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from .config import settings
from .db import Base, SessionLocal, engine, get_db
from .models import Shop
from . import clock
from .routers import auth, calls, customers, dev, entries, incoming, messages, metrics, pay, sim
from .routers import settings as settings_router
from .services.scheduler import run_scheduler
from .services.auth import shop_for_token
from .services.shop import current_shop_id, get_or_create_shop
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
        get_or_create_shop(db)  # make sure the local shop exists
        for shop in db.scalars(select(Shop)).all():  # every shop's reminders
            run_scheduler(db, shop)


async def reminder_timer():
    """Runs the reminder timer once a minute. The database work runs in a
    worker thread so it never blocks the web server."""
    while True:
        try:
            await asyncio.to_thread(_tick)
        except Exception:  # keep the timer alive; log and try again next minute
            logging.exception("Reminder timer failed")
        await asyncio.sleep(60)


# Customer-facing pages opened by an unguessable link, and login itself, don't need a shop login.
PUBLIC_PREFIXES = ("/api/auth/", "/api/pay/", "/api/sim/", "/api/health")


async def auth_step(request: Request, db: Session = Depends(get_db)):
    """Runs before every request: works out which shop is logged in.

    It's async on purpose: the shop id it records must be visible to the
    endpoint that runs next (see services/shop.py)."""
    header = request.headers.get("authorization", "")
    token = header[7:].strip() if header.lower().startswith("bearer ") else None
    shop = shop_for_token(db, token) if token else None
    current_shop_id.set(shop.id if shop else None)
    path = request.url.path
    if settings.auth_required and shop is None and path.startswith("/api/") and not path.startswith(PUBLIC_PREFIXES):
        raise HTTPException(401, "Please log in")


app = FastAPI(title="Credit dues assistant (concept prototype)", lifespan=lifespan, dependencies=[Depends(auth_step)])
app.include_router(auth.router)
app.include_router(settings_router.router)
app.include_router(entries.router)
app.include_router(customers.router)
app.include_router(calls.router)
app.include_router(metrics.router)
app.include_router(messages.router)
app.include_router(pay.router)
app.include_router(incoming.router)
app.include_router(sim.router)  # simulation-only endpoints
app.include_router(dev.router)  # demo clock


@app.get("/api/health")
def health():
    return {"ok": True, "messaging": "simulated", "payments": "simulated"}
