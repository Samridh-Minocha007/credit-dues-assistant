from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import Customer
from ..schemas import (
    CallOutcomeOut,
    CustomerDetail,
    CustomerSummary,
    DueOut,
    MessageOut,
    PaymentIn,
    PaymentOut,
    PaymentResultOut,
    PromiseOut,
)
from ..services.collections import collection_info
from ..services.customers import CustomerRow, list_customers
from ..services.messaging import pay_link
from ..services.money import to_paise
from ..services.payments import PaymentError, record_payment
from ..services.privacy import PrivacyError, delete_customer_data, opt_in, opt_out
from ..services.shop import get_or_create_shop

router = APIRouter(prefix="/api/customers", tags=["customers"])


def _summary(r: CustomerRow) -> CustomerSummary:
    return CustomerSummary(
        id=r.customer.id,
        phone=r.customer.phone,
        name=r.customer.name,
        balance_paise=r.balance_paise,
        open_dues=r.open_dues,
        oldest_open_due_at=r.oldest_open_due_at,
        opted_out=r.customer.opted_out_at is not None,
        deleted=r.customer.deleted_at is not None,
    )


@router.get("", response_model=list[CustomerSummary])
def search_customers(q: str | None = Query(default=None, max_length=50), db: Session = Depends(get_db)):
    """Used for the list screen and for autocomplete while typing a phone number."""
    return [_summary(r) for r in list_customers(db, get_or_create_shop(db), q=q)]


def _get(db: Session, customer_id: int) -> Customer:
    shop = get_or_create_shop(db)
    c = db.get(Customer, customer_id)
    if c is None or c.shop_id != shop.id:
        raise HTTPException(404, "Customer not found")
    return c


@router.get("/{customer_id}", response_model=CustomerDetail)
def get_customer(customer_id: int, db: Session = Depends(get_db)):
    c = _get(db, customer_id)
    open_dues = [d for d in c.dues if d.status == "open"]
    info = collection_info(get_or_create_shop(db), c)
    return CustomerDetail(
        id=c.id,
        phone=c.phone,
        name=c.name,
        balance_paise=sum(d.balance_paise for d in open_dues),
        open_dues=len(open_dues),
        oldest_open_due_at=min((d.created_at for d in open_dues), default=None),
        opted_out=c.opted_out_at is not None,
        consent_at=c.consent_at,
        consent_method=c.consent_method,
        created_at=c.created_at,
        deleted=c.deleted_at is not None,
        deleted_at=c.deleted_at,
        pay_link=pay_link(c) if c.pay_token else None,
        # Newest first everywhere, so the latest activity is at the top.
        dues=[DueOut.model_validate(d) for d in reversed(c.dues)],
        payments=[PaymentOut.model_validate(p) for p in reversed(c.payments)],
        messages=[MessageOut.model_validate(m) for m in reversed(c.messages)],
        collection_state=info.state if info else None,
        collection_reason=info.reason if info else None,
        promises=[PromiseOut.model_validate(p) for p in reversed(c.promises)],
        call_outcomes=[CallOutcomeOut.model_validate(o) for o in reversed(c.call_outcomes)],
    )


@router.post("/{customer_id}/payments", response_model=PaymentResultOut)
def record_cash_payment(customer_id: int, body: PaymentIn, db: Session = Depends(get_db)):
    """Customer paid at the counter (cash or their own UPI). Same rules as the
    payment link: oldest dues are cleared first."""
    c = _get(db, customer_id)
    try:
        r = record_payment(db, get_or_create_shop(db), c, to_paise(body.amount), source="cash")
    except PaymentError as e:
        raise HTTPException(422, str(e))
    return PaymentResultOut.build(r)



@router.post("/{customer_id}/opt-out", response_model=CustomerDetail)
def stop_messages(customer_id: int, db: Session = Depends(get_db)):
    """Shopkeeper stops all messages to this customer (e.g. they asked in person)."""
    opt_out(db, _get(db, customer_id))
    db.commit()
    return get_customer(customer_id, db)


@router.post("/{customer_id}/opt-in", response_model=CustomerDetail)
def resume_messages(customer_id: int, db: Session = Depends(get_db)):
    try:
        opt_in(db, _get(db, customer_id))
    except PrivacyError as e:
        raise HTTPException(422, str(e))
    db.commit()
    return get_customer(customer_id, db)


@router.delete("/{customer_id}", response_model=CustomerDetail)
def delete_customer(customer_id: int, db: Session = Depends(get_db)):
    """Erase personal data on the customer's request. Keeps name, amounts and dates."""
    try:
        delete_customer_data(db, _get(db, customer_id))
    except PrivacyError as e:
        raise HTTPException(422, str(e))
    return get_customer(customer_id, db)
