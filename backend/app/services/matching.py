"""Working out which customer a UPI payment came from ("matching").

Customers pay to the shop's single UPI ID, so a payment arrives as just
"Rs 500 from RAMESH K (9876543210@ybl), note: 'Ramesh dues C12'". We sort it
into one of three buckets:

  STRONG evidence -> mark it paid automatically
     1. the note still carries our customer reference ("C12"), or
     2. the payer's UPI ID was confirmed for a customer before.

  WEAK evidence -> ask the shopkeeper with a one-tap card
     3. exactly the amount a customer owes, or the payer's name matches a
        customer who owes money. Never auto-marked: two people can owe the
        same amount or share a first name.

  NO evidence -> treat as an ordinary sale and leave it alone
     Most UPI payments at a kirana are for today's shopping, not old dues.
     Asking about every one would bury the shopkeeper in questions.

Strong evidence that doesn't fit (paying more than is owed, or paying when
nothing is pending, which may be a double payment) also goes to the
shopkeeper instead of being guessed.

Every decision stores a plain-language reason, shown on the card.
"""
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import clock
from ..models import Customer, CustomerUpiId, IncomingPayment, Shop
from .money import format_rupees
from .payments import customer_balance, record_payment
from .upi import parse_ref


class MatchError(ValueError):
    pass


def _label(c: Customer) -> str:
    return c.name or c.phone


def _learn_upi_id(db: Session, shop: Shop, customer: Customer, vpa: str) -> None:
    """Remember that this UPI ID belongs to this customer (re-assign if it was
    linked to someone else; the latest confirmation wins)."""
    row = db.scalar(select(CustomerUpiId).where(CustomerUpiId.shop_id == shop.id, CustomerUpiId.vpa == vpa))
    if row is None:
        db.add(CustomerUpiId(shop_id=shop.id, customer_id=customer.id, vpa=vpa, learned_at=clock.now()))
    else:
        row.customer_id = customer.id


def _apply(db: Session, shop: Shop, inc: IncomingPayment, customer: Customer, amount_paise: int) -> None:
    result = record_payment(db, shop, customer, amount_paise, source="upi")  # commits, sends receipt
    inc.customer_id = customer.id
    inc.payment_id = result.payment.id


def _first_word(name: str | None) -> str:
    return (name or "").strip().split(" ")[0].lower()


def handle_incoming(
    db: Session, shop: Shop, *, payer_vpa: str, payer_name: str | None, amount_paise: int, note: str | None
) -> IncomingPayment:
    vpa = payer_vpa.strip().lower()
    inc = IncomingPayment(
        shop_id=shop.id,
        payer_vpa=vpa,
        payer_name=(payer_name or "").strip() or None,
        amount_paise=amount_paise,
        note=(note or "").strip() or None,
        received_at=clock.now(),
        status="not_dues",
        match_reason="",
    )
    db.add(inc)
    amount = format_rupees(amount_paise)

    # --- 1. Our reference in the note ("Ramesh dues C12") ---
    # Checked first: it comes from the link sent to that exact customer, so it
    # beats a learned UPI ID (e.g. a parent paying a child's tab).
    ref = parse_ref(note)
    c = db.get(Customer, ref) if ref else None
    if c is not None and c.shop_id == shop.id:
        bal = customer_balance(c)
        inc.customer_id = c.id
        if 0 < amount_paise <= bal:
            inc.status, inc.match_reason = "matched_auto", f"Payment note has {_label(c)}'s reference (C{ref})"
            _learn_upi_id(db, shop, c, vpa)  # next time, even without the note
            _apply(db, shop, inc, c, amount_paise)
        elif bal == 0:
            inc.status = "needs_review"
            inc.match_reason = f"Note says {_label(c)}, but nothing is pending: possibly paid twice"
        else:
            inc.status = "needs_review"
            inc.match_reason = f"Note says {_label(c)}, but Rs {amount} is more than the Rs {format_rupees(bal)} pending"
        db.commit()
        return inc

    # --- 2. A UPI ID we've learned before ---
    learned = db.scalar(select(CustomerUpiId).where(CustomerUpiId.shop_id == shop.id, CustomerUpiId.vpa == vpa))
    if learned is not None:
        c = db.get(Customer, learned.customer_id)
        bal = customer_balance(c)
        inc.customer_id = c.id
        if bal == 0:
            inc.status, inc.match_reason = "not_dues", f"From {_label(c)}'s UPI ID, but nothing is pending: treated as a regular sale"
        elif amount_paise <= bal:
            inc.status, inc.match_reason = "matched_auto", f"From {_label(c)}'s known UPI ID"
            _apply(db, shop, inc, c, amount_paise)
        else:
            inc.status = "needs_review"
            inc.match_reason = f"From {_label(c)}'s UPI ID, but Rs {amount} is more than the Rs {format_rupees(bal)} pending (maybe includes today's shopping)"
        db.commit()
        return inc

    # --- 3. Weak hints: exact amount owed, or same first name ---
    owing = [
        (cust, customer_balance(cust))
        for cust in db.scalars(select(Customer).where(Customer.shop_id == shop.id, Customer.deleted_at.is_(None)))
    ]
    owing = [(cust, bal) for cust, bal in owing if bal > 0]
    payer_first = _first_word(payer_name)
    hints: dict[int, tuple[Customer, str]] = {}
    for cust, bal in owing:
        if bal == amount_paise:
            hints[cust.id] = (cust, f"amount matches what {_label(cust)} owes")
        elif len(payer_first) >= 3 and payer_first == _first_word(cust.name):
            hints[cust.id] = (cust, f"payer name '{payer_name}' looks like {_label(cust)}")

    if len(hints) == 1:
        (cust, why), = hints.values()
        inc.status, inc.customer_id = "needs_review", cust.id  # customer_id here = our suggestion
        inc.match_reason = f"Possibly {_label(cust)}: {why}"
    elif len(hints) > 1:
        inc.status = "needs_review"
        inc.match_reason = "Could be " + " or ".join(_label(c) for c, _ in hints.values())
    else:
        inc.status, inc.match_reason = "not_dues", "No sign this is for dues: treated as a regular sale"
    db.commit()
    return inc


def confirm(db: Session, shop: Shop, inc: IncomingPayment, customer: Customer) -> IncomingPayment:
    """Shopkeeper tapped "Yes, this was <customer>"."""
    if inc.payment_id is not None:
        raise MatchError("This payment is already matched")
    bal = customer_balance(customer)
    if bal == 0:
        raise MatchError(f"{_label(customer)} has nothing pending")
    # If they paid more than they owe, the rest was most likely today's
    # shopping: apply only what's owed.
    applied = min(inc.amount_paise, bal)
    _learn_upi_id(db, shop, customer, inc.payer_vpa)
    inc.status = "matched_confirmed"
    inc.match_reason = f"Confirmed by shopkeeper as {_label(customer)}" + (
        f"; Rs {format_rupees(applied)} applied to dues, rest treated as a sale" if applied < inc.amount_paise else ""
    )
    _apply(db, shop, inc, customer, applied)
    db.commit()
    return inc


def dismiss(db: Session, inc: IncomingPayment) -> IncomingPayment:
    """Shopkeeper tapped "Not for dues" (e.g. a regular sale)."""
    if inc.payment_id is not None:
        raise MatchError("This payment is already matched")
    inc.status, inc.customer_id = "not_dues", None
    inc.match_reason = "Marked by shopkeeper as not for dues"
    db.commit()
    return inc
