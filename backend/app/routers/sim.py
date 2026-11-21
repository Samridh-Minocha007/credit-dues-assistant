"""SIMULATION ONLY. Stand-ins for things a real deployment gets from outside:

- the bank / merchant app telling us "money arrived" (in production, a
  webhook from the payment provider), and
- the customer's phone, to demo what the customer sees.
"""
from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import get_db
from ..schemas import BankNotificationIn, IncomingPaymentOut, MessageOut, PhoneOut, ReplyIn
from ..services.matching import handle_incoming
from ..services.money import to_paise
from ..services.privacy import handle_reply
from ..models import Shop
from ..services.shop import get_or_create_shop, shop_of
from .incoming import to_out
from .pay import by_token

router = APIRouter(prefix="/api/sim", tags=["simulation"])


@router.post("/bank-notification", response_model=IncomingPaymentOut, status_code=201)
def bank_notification(body: BankNotificationIn, db: Session = Depends(get_db)):
    # Like a real payment notification, the payee UPI ID says which shop was paid.
    shop = None
    if body.payee_vpa:
        shop = db.scalar(select(Shop).where(Shop.upi_id == body.payee_vpa.strip().lower()))
    inc = handle_incoming(
        db,
        shop or get_or_create_shop(db),
        payer_vpa=body.payer_vpa,
        payer_name=body.payer_name,
        amount_paise=to_paise(body.amount),
        note=body.note,
    )
    return to_out(inc)


@router.get("/phone/{token}", response_model=PhoneOut)
def phone(token: str, db: Session = Depends(get_db)):
    c = by_token(db, token)
    shop = shop_of(db, c)
    # The customer only sees what actually reaches them (or will, in the
    # morning) and what they sent. Never blocked or cancelled messages.
    visible = [m for m in c.messages if m.status in ("sent_sim", "scheduled", "received")]
    return PhoneOut(
        shop_name=shop.name,
        customer_name=c.name,
        pay_token=c.pay_token,
        messages=[MessageOut.model_validate(m) for m in visible],  # oldest first, like a chat
    )


@router.post("/phone/{token}/reply", response_model=PhoneOut)
def reply(token: str, body: ReplyIn, db: Session = Depends(get_db)):
    """The customer types a message to the shop on their (simulated) phone."""
    c = by_token(db, token)
    handle_reply(db, shop_of(db, c), c, body.text)
    return phone(token, db)
