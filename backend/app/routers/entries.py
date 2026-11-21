from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..db import get_db
from ..schemas import CustomerSummary, DueOut, EntryIn, EntryOut, MessageOut, VoiceIn, VoiceOut
from ..services.customers import effective_limit, list_customers
from ..services.entries import EntryError, ItemInput, record_entry
from ..services.phone import InvalidPhone
from ..services.shop import get_or_create_shop

router = APIRouter(prefix="/api/entries", tags=["entries"])


@router.post("", response_model=EntryOut, status_code=201)
def create_entry(body: EntryIn, db: Session = Depends(get_db)):
    shop = get_or_create_shop(db)
    try:
        result = record_entry(
            db,
            shop,
            phone=body.phone,
            bill_amount=body.bill_amount,
            amount_paid=body.amount_paid,
            name=body.name,
            items=[ItemInput(i.description, i.qty, i.amount) for i in body.items],
        )
    except (InvalidPhone, EntryError) as e:
        raise HTTPException(422, str(e))

    # Return the customer's new total so the screen can show "Ramesh now owes Rs 840".
    row = next(r for r in list_customers(db, shop, q=result.customer.phone) if r.customer.id == result.customer.id)
    return EntryOut(
        customer=CustomerSummary(
            id=row.customer.id,
            phone=row.customer.phone,
            name=row.customer.name,
            balance_paise=row.balance_paise,
            open_dues=row.open_dues,
            oldest_open_due_at=row.oldest_open_due_at,
            opted_out=row.customer.opted_out_at is not None,
            deleted=False,
            credit_limit_paise=effective_limit(shop, row.customer),
            own_credit_limit_paise=row.customer.credit_limit_paise,
        ),
        over_limit=(lambda lim: lim is not None and row.balance_paise > lim)(effective_limit(shop, row.customer)),
        due=DueOut.model_validate(result.due),
        is_new_customer=result.is_new_customer,
        message=MessageOut.model_validate(result.message),
    )


@router.post("/parse-voice", response_model=VoiceOut)
def parse_voice_entry(body: VoiceIn, db: Session = Depends(get_db)):
    """Fill the entry form from what the shopkeeper said. Never saves anything."""
    from sqlalchemy import select

    from ..models import Customer
    from ..services.voice import parse_voice

    shop = get_or_create_shop(db)
    customers = db.scalars(select(Customer).where(Customer.shop_id == shop.id, Customer.deleted_at.is_(None))).all()
    return parse_voice(body.text, customers).__dict__
