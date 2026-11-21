"""Recording money received, and crossing off the oldest dues first."""
from dataclasses import dataclass

from sqlalchemy.orm import Session

from .. import clock
from ..models import Customer, Message, Payment, Shop
from . import templates
from .messaging import queue_message
from .money import format_rupees


class PaymentError(ValueError):
    pass


@dataclass
class PaymentResult:
    payment: Payment
    balance_paise: int  # what the customer still owes after this payment
    receipt: Message


def customer_balance(customer: Customer) -> int:
    return sum(d.balance_paise for d in customer.dues if d.status == "open")


def record_payment(db: Session, shop: Shop, customer: Customer, amount_paise: int, source: str) -> PaymentResult:
    balance = customer_balance(customer)
    if amount_paise <= 0:
        raise PaymentError("Amount must be more than 0")
    if balance == 0:
        raise PaymentError("Nothing is pending")
    if amount_paise > balance:
        # Advance payments / store credit are out of scope for now.
        raise PaymentError(f"Amount is more than the pending Rs {format_rupees(balance)}")

    now = clock.now()
    payment = Payment(customer=customer, amount_paise=amount_paise, source=source, paid_at=now)
    db.add(payment)

    # Oldest first: customer.dues is already ordered by created_at.
    left = amount_paise
    for due in customer.dues:
        if left == 0:
            break
        if due.status != "open":
            continue
        used = min(left, due.balance_paise)
        due.balance_paise -= used
        left -= used
        if due.balance_paise == 0:
            due.status = "paid"
            due.closed_at = now  # this timestamp drives the "recovered within 30 days" metric

    remaining = balance - amount_paise
    if remaining == 0:
        for p in customer.promises:
            if p.status == "pending":
                p.status = "kept"
    receipt = queue_message(
        db,
        shop,
        customer,
        "payment_receipt",
        templates.payment_receipt(
            name=customer.name, shop=shop.name, paid=format_rupees(amount_paise), remaining=format_rupees(remaining),
            lang=shop.message_language,
        ),
    )
    db.commit()
    return PaymentResult(payment=payment, balance_paise=remaining, receipt=receipt)
