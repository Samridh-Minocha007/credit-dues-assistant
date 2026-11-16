"""DEMO ONLY: the time machine.

Weekly reminders and a 30-day escalation can't be shown live if you have to
wait real weeks. These endpoints move the app's clock forward and run the
reminder timer straight away, so a demo can show "three Sundays later" in
seconds. The jump is saved, so restarting the server keeps the demo time.
"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from .. import clock
from ..db import get_db
from ..schemas import AdvanceIn, ClockOut, RunOut
from ..services.scheduler import run_scheduler
from ..services.shop import get_or_create_shop

router = APIRouter(prefix="/api/dev", tags=["demo clock"])


def _run_out(summary) -> RunOut:
    return RunOut(now=clock.now(), **{k: getattr(summary, k) for k in ("delivered", "reminders_sent", "blocked_cap", "cancelled_paid", "promise_followups", "promises_broken", "slots")})


@router.get("/clock", response_model=ClockOut)
def get_clock():
    return ClockOut(now=clock.now(), offset_seconds=clock.offset_seconds())


@router.post("/advance", response_model=RunOut)
def advance(body: AdvanceIn, db: Session = Depends(get_db)):
    shop = get_or_create_shop(db)
    if shop.scheduler_last_run_at is None:
        shop.scheduler_last_run_at = clock.now()  # count slots from here, not from the jump target
    clock.advance(days=body.days, hours=body.hours)
    shop.demo_clock_offset_s = clock.offset_seconds()
    return _run_out(run_scheduler(db, shop))


@router.post("/reset-clock", response_model=ClockOut)
def reset_clock(db: Session = Depends(get_db)):
    """Back to real time. The timer restarts from now, so nothing is replayed."""
    shop = get_or_create_shop(db)
    clock.reset()
    shop.demo_clock_offset_s = 0
    shop.scheduler_last_run_at = clock.now()
    db.commit()
    return ClockOut(now=clock.now(), offset_seconds=0)


@router.post("/run-scheduler", response_model=RunOut)
def run_now(db: Session = Depends(get_db)):
    return _run_out(run_scheduler(db, get_or_create_shop(db)))
