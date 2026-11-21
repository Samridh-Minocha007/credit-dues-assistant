"""The payment link in messages: /pay/<token>.

WhatsApp doesn't make upi:// links tappable, so messages carry a normal web
link. This page returns a UPI link that opens the customer's UPI app with
the SHOP's own UPI ID, the current balance and a note pre-filled. The money
goes straight to the shop; this server never touches it.

Found by the random token, not the customer id, so a link only ever opens
its own customer's page.
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import Customer
from .. import clock
from ..schemas import PayPageOut, StatementLineOut, StatementOut
from ..services.statement import statement_lines
from ..services.payments import customer_balance
from ..services.shop import shop_of
from ..services.upi import payment_note, upi_link

router = APIRouter(prefix="/api/pay", tags=["payment link"])


def by_token(db: Session, token: str) -> Customer:
    c = db.scalar(select(Customer).where(Customer.pay_token == token))
    if c is None:
        raise HTTPException(404, "This payment link is not valid")
    return c


@router.get("/{token}", response_model=PayPageOut)
def pay_page(token: str, db: Session = Depends(get_db)):
    c = by_token(db, token)
    shop = shop_of(db, c)
    bal = customer_balance(c)
    return PayPageOut(
        shop_name=shop.name,
        shop_upi_id=shop.upi_id,
        customer_name=c.name,
        balance_paise=bal,
        upi_link=upi_link(shop, c, bal) if shop.upi_id else None,
        note=payment_note(c),
        # Many people's UPI ID is their phone number @ their bank app's handle.
        demo_payer_vpa=f"{c.phone}@ybl",
        demo_payer_name=(c.name or "Customer").upper(),
    )


@router.get("/{token}/statement", response_model=StatementOut)
def statement(token: str, db: Session = Depends(get_db)):
    """The customer's statement, opened from the link in their message."""
    c = by_token(db, token)
    shop = shop_of(db, c)
    return StatementOut(
        shop_name=shop.name,
        customer_name=c.name,
        generated_at=clock.now(),
        balance_paise=customer_balance(c),
        lines=[StatementLineOut(**l.__dict__) for l in statement_lines(c)],
    )
