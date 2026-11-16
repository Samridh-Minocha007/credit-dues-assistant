"""Step 4-5 of the core loop: the call list, and what the shopkeeper taps
after calling ("promised a date", "disputed", "written off")."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import Customer
from ..schemas import CallCardOut, CallListOut, CallOutcomeOut, OutcomeIn, PromiseOut, ResolveIn
from ..services.collections import CollectionInfo, OutcomeError, call_list, record_outcome, resolve_dispute
from ..services.shop import get_or_create_shop

router = APIRouter(prefix="/api", tags=["calls"])


def _card(i: CollectionInfo) -> CallCardOut:
    return CallCardOut(
        customer_id=i.customer.id,
        name=i.customer.name,
        phone=i.customer.phone,
        balance_paise=i.balance_paise,
        oldest_due_at=i.oldest_due_at,
        oldest_age_days=i.oldest_age_days,
        reason=i.reason,
        last_reminder_at=i.last_reminder_at,
        latest_promise=PromiseOut.model_validate(i.latest_promise) if i.latest_promise else None,
    )


def _customer(db: Session, customer_id: int) -> Customer:
    c = db.get(Customer, customer_id)
    if c is None or c.shop_id != get_or_create_shop(db).id:
        raise HTTPException(404, "Customer not found")
    return c


@router.get("/call-list", response_model=CallListOut)
def get_call_list(db: Session = Depends(get_db)):
    groups = call_list(db, get_or_create_shop(db))
    return CallListOut(**{k: [_card(i) for i in v] for k, v in groups.items()})


@router.post("/customers/{customer_id}/call-outcome", response_model=CallOutcomeOut, status_code=201)
def call_outcome(customer_id: int, body: OutcomeIn, db: Session = Depends(get_db)):
    c = _customer(db, customer_id)
    try:
        return record_outcome(db, get_or_create_shop(db), c, body.outcome, promised_date=body.promised_date, note=body.note)
    except OutcomeError as e:
        raise HTTPException(422, str(e))


@router.post("/customers/{customer_id}/resolve-dispute", response_model=CallOutcomeOut, status_code=201)
def resolve(customer_id: int, body: ResolveIn, db: Session = Depends(get_db)):
    try:
        return resolve_dispute(db, _customer(db, customer_id), body.note)
    except OutcomeError as e:
        raise HTTPException(422, str(e))
