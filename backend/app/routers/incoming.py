"""The shopkeeper's "Payments" inbox: UPI payments the app couldn't match
for sure, each with a one-tap "Yes, it's <customer>" / "Not for dues"."""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import Customer, IncomingPayment
from ..schemas import ConfirmIn, IncomingPaymentOut
from ..services.matching import MatchError, confirm, dismiss
from ..services.payments import customer_balance
from ..services.shop import get_or_create_shop

router = APIRouter(prefix="/api/incoming-payments", tags=["incoming payments"])


def to_out(inc: IncomingPayment) -> IncomingPaymentOut:
    out = IncomingPaymentOut.model_validate(inc)
    if inc.customer is not None:
        c = inc.customer
        out.customer_name = c.name or ("Deleted customer" if c.deleted_at else c.phone)
        out.customer_balance_paise = customer_balance(inc.customer)
    return out


def _get(db: Session, payment_id: int) -> IncomingPayment:
    inc = db.get(IncomingPayment, payment_id)
    if inc is None or inc.shop_id != get_or_create_shop(db).id:
        raise HTTPException(404, "Payment not found")
    return inc


@router.get("", response_model=list[IncomingPaymentOut])
def list_incoming(status: str | None = Query(default=None), db: Session = Depends(get_db)):
    shop = get_or_create_shop(db)
    stmt = (
        select(IncomingPayment)
        .where(IncomingPayment.shop_id == shop.id)
        .order_by(IncomingPayment.received_at.desc(), IncomingPayment.id.desc())
        .limit(200)
    )
    if status:
        stmt = stmt.where(IncomingPayment.status == status)
    return [to_out(i) for i in db.scalars(stmt)]


@router.post("/{payment_id}/confirm", response_model=IncomingPaymentOut)
def confirm_payment(payment_id: int, body: ConfirmIn, db: Session = Depends(get_db)):
    shop = get_or_create_shop(db)
    inc = _get(db, payment_id)
    c = db.get(Customer, body.customer_id)
    if c is None or c.shop_id != shop.id:
        raise HTTPException(404, "Customer not found")
    try:
        return to_out(confirm(db, shop, inc, c))
    except MatchError as e:
        raise HTTPException(422, str(e))


@router.post("/{payment_id}/dismiss", response_model=IncomingPaymentOut)
def dismiss_payment(payment_id: int, db: Session = Depends(get_db)):
    try:
        return to_out(dismiss(db, _get(db, payment_id)))
    except MatchError as e:
        raise HTTPException(422, str(e))
