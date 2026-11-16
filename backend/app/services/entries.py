"""Step 1 of the core loop: record a credit sale in one go.

One call does everything: find the customer by phone (or create them), and
record the unpaid part of the bill as a due. The shop screen therefore needs
a single tap, which is how we keep entry under 5 seconds.
"""
from dataclasses import dataclass
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import clock
from ..models import Customer, Due, LineItem, Message, Shop
from ..upgrade import new_pay_token
from . import templates
from .messaging import pay_link, queue_message
from .money import format_rupees, to_paise
from .phone import normalize_phone


class EntryError(ValueError):
    pass


@dataclass
class ItemInput:
    description: str
    qty: str | None = None
    amount: Decimal | None = None


@dataclass
class EntryResult:
    customer: Customer
    due: Due
    is_new_customer: bool
    message: Message  # the bill notice (sent, scheduled for morning, or blocked)


def find_customer(db: Session, shop: Shop, phone: str) -> Customer | None:
    return db.scalar(select(Customer).where(Customer.shop_id == shop.id, Customer.phone == phone))


def record_entry(
    db: Session,
    shop: Shop,
    *,
    phone: str,
    bill_amount: Decimal,
    amount_paid: Decimal,
    name: str | None = None,
    items: list[ItemInput] | None = None,
) -> EntryResult:
    phone = normalize_phone(phone)
    bill = to_paise(bill_amount)
    paid = to_paise(amount_paid)
    if bill <= 0:
        raise EntryError("Bill amount must be more than 0")
    if paid < 0:
        raise EntryError("Amount paid cannot be negative")
    if paid >= bill:
        # Fully paid sales are not credit, so there is nothing to track.
        raise EntryError("Nothing is owed on this bill")

    now = clock.now()
    name = (name or "").strip() or None

    customer = find_customer(db, shop, phone)
    is_new = customer is None
    if is_new:
        customer = Customer(
            shop_id=shop.id, phone=phone, name=name, consent_at=now, created_at=now, pay_token=new_pay_token()
        )
        db.add(customer)
    elif name:
        customer.name = name  # shopkeeper corrected or added the name

    due = Due(
        customer=customer,
        bill_paise=bill,
        paid_at_entry_paise=paid,
        balance_paise=bill - paid,
        status="open",
        created_at=now,
    )
    for it in items or []:
        if it.description.strip():
            due.items.append(
                LineItem(
                    description=it.description.strip(),
                    qty=(it.qty or "").strip() or None,
                    amount_paise=to_paise(it.amount) if it.amount is not None else None,
                )
            )
    db.add(due)

    # Step 2 of the core loop: tell the customer, with their payment link.
    total = sum(d.balance_paise for d in customer.dues if d.status == "open")
    message = queue_message(
        db,
        shop,
        customer,
        "bill_notice",
        templates.bill_notice(
            name=customer.name,
            shop=shop.name,
            credit=format_rupees(due.balance_paise),
            total=format_rupees(total),
            link=pay_link(customer) if shop.upi_id else None,
        ),
    )
    db.commit()
    return EntryResult(customer=customer, due=due, is_new_customer=is_new, message=message)
