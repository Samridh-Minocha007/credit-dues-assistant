"""SIMULATION ONLY. Stand-ins for things a real deployment gets from outside:

- the bank / merchant app telling us "money arrived" (in production, a
  webhook from the payment provider), and
- the customer's phone, to demo what the customer sees.
"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..db import get_db
from ..schemas import BankNotificationIn, IncomingPaymentOut, MessageOut, PhoneOut
from ..services.matching import handle_incoming
from ..services.money import to_paise
from ..services.shop import get_or_create_shop
from .incoming import to_out
from .pay import by_token

router = APIRouter(prefix="/api/sim", tags=["simulation"])


@router.post("/bank-notification", response_model=IncomingPaymentOut, status_code=201)
def bank_notification(body: BankNotificationIn, db: Session = Depends(get_db)):
    inc = handle_incoming(
        db,
        get_or_create_shop(db),
        payer_vpa=body.payer_vpa,
        payer_name=body.payer_name,
        amount_paise=to_paise(body.amount),
        note=body.note,
    )
    return to_out(inc)


@router.get("/phone/{token}", response_model=PhoneOut)
def phone(token: str, db: Session = Depends(get_db)):
    c = by_token(db, token)
    shop = get_or_create_shop(db)
    # The customer only sees messages that were (or will be) delivered,
    # never ones blocked because they opted out.
    visible = [m for m in c.messages if m.status != "blocked_opt_out"]
    return PhoneOut(
        shop_name=shop.name,
        customer_name=c.name,
        pay_token=c.pay_token,
        messages=[MessageOut.model_validate(m) for m in visible],  # oldest first, like a chat
    )
