"""Who needs a phone call, and what happens after the call.

Every customer who owes money is in exactly one state:

  "reminders"  normal: weekly reminders go out automatically
  "promised"   they promised a date that hasn't passed: reminders pause
  "to_call"    past the call rule: reminders STOP, shopkeeper should call
  "disputed"   they disagree with the amount: no messages, no calls,
               until the shopkeeper resolves it or writes it off

The call rule (set in Settings, defaults from the brief):
  oldest unpaid bill >= escalation_days (30)
  OR balance >= escalation_amount (Rs 2,000) and oldest bill >= escalation_min_days (14)

The state is worked out fresh each time from the customer's bills, promises
and dispute flag, instead of being stored. So it can never be stale: a
payment, a new promise or a changed setting takes effect immediately.

Why a promise beats the call rule: if the shopkeeper calls and the customer
promises Friday, they shouldn't stay on the call list until Friday. If
Friday passes unpaid, the promise is broken and the call rule applies again.
"""
from dataclasses import dataclass
from datetime import date, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import clock
from ..models import CallOutcome, Customer, Promise, Shop
from .money import format_rupees
from .payments import customer_balance

OUTCOMES = {"promised_date", "disputed", "written_off"}
MAX_PROMISE_DAYS = 60


class OutcomeError(ValueError):
    pass


@dataclass
class CollectionInfo:
    customer: Customer
    state: str  # reminders | promised | to_call | disputed
    balance_paise: int
    oldest_due_at: datetime
    oldest_age_days: int
    reason: str  # plain language, shown on the call card
    last_reminder_at: datetime | None
    latest_promise: Promise | None


def latest_promise(c: Customer) -> Promise | None:
    live = [p for p in c.promises if p.status != "replaced"]
    return live[-1] if live else None


def active_promise(c: Customer, today: date) -> Promise | None:
    p = latest_promise(c)
    return p if p and p.status == "pending" and p.promised_date >= today else None


def last_reminder_at(c: Customer) -> datetime | None:
    sent = [m.sent_at for m in c.messages if m.kind in ("weekly_reminder", "promise_followup") and m.status == "sent_sim" and m.sent_at]
    return max(sent) if sent else None


def collection_info(shop: Shop, c: Customer, now: datetime | None = None) -> CollectionInfo | None:
    """None if the customer owes nothing (or their data was deleted)."""
    now = now or clock.now()
    if c.deleted_at is not None:
        return None
    open_dues = [d for d in c.dues if d.status == "open"]
    if not open_dues:
        return None
    balance = customer_balance(c)
    oldest = min(d.created_at for d in open_dues)
    age = (now - oldest).days
    promise = latest_promise(c)

    over_days = age >= shop.escalation_days
    over_amount = balance >= shop.escalation_amount_paise and age >= shop.escalation_min_days

    if c.collection_status == "disputed":
        state, reason = "disputed", "Disputed the amount"
    elif active_promise(c, now.date()):
        state, reason = "promised", f"Promised to pay by {promise.promised_date:%a %d %b}"
    elif over_days:
        state, reason = "to_call", f"Oldest bill is {age} days old"
    elif over_amount:
        state, reason = "to_call", f"Owes Rs {format_rupees(balance)}, oldest bill {age} days old"
    else:
        state, reason = "reminders", "Getting weekly reminders"

    if state == "to_call" and promise and promise.status == "broken":
        reason += f". Promised {promise.promised_date:%d %b}, didn't pay"

    return CollectionInfo(c, state, balance, oldest, age, reason, last_reminder_at(c), promise)


def gets_automatic_reminders(shop: Shop, c: Customer, at: datetime) -> bool:
    info = collection_info(shop, c, at)
    return info is not None and info.state == "reminders"


def call_list(db: Session, shop: Shop) -> dict[str, list[CollectionInfo]]:
    now = clock.now()
    groups: dict[str, list[CollectionInfo]] = {"to_call": [], "promised": [], "disputed": []}
    for c in db.scalars(select(Customer).where(Customer.shop_id == shop.id, Customer.deleted_at.is_(None))):
        info = collection_info(shop, c, now)
        if info and info.state in groups:
            groups[info.state].append(info)
    groups["to_call"].sort(key=lambda i: (-i.oldest_age_days, -i.balance_paise))  # longest waiting first
    groups["promised"].sort(key=lambda i: i.latest_promise.promised_date)
    groups["disputed"].sort(key=lambda i: -i.balance_paise)
    return groups


def _replace_pending_promises(c: Customer) -> None:
    for p in c.promises:
        if p.status == "pending":
            p.status = "replaced"


def record_outcome(
    db: Session, shop: Shop, c: Customer, outcome: str, *, promised_date: date | None = None, note: str | None = None
) -> CallOutcome:
    """The shopkeeper tapped an outcome after calling."""
    if outcome not in OUTCOMES:
        raise OutcomeError("Unknown outcome")
    if c.deleted_at is not None:
        raise OutcomeError("This customer's data was deleted")
    balance = customer_balance(c)
    if balance == 0:
        raise OutcomeError("Nothing is pending for this customer")

    now = clock.now()
    note = (note or "").strip() or None
    row = CallOutcome(customer=c, outcome=outcome, note=note, balance_paise=balance, created_at=now)
    db.add(row)

    if outcome == "promised_date":
        today = now.date()
        if promised_date is None:
            raise OutcomeError("Pick the date they promised")
        if promised_date < today:
            raise OutcomeError("The promised date can't be in the past")
        if promised_date > today + timedelta(days=MAX_PROMISE_DAYS):
            raise OutcomeError(f"Pick a date within {MAX_PROMISE_DAYS} days")
        _replace_pending_promises(c)
        promise = Promise(customer=c, promised_date=promised_date, source="call", status="pending", created_at=now)
        db.add(promise)
        c.collection_status = "normal"
        db.flush()
        row.promise_id = promise.id

    elif outcome == "disputed":
        _replace_pending_promises(c)
        c.collection_status = "disputed"

    elif outcome == "written_off":
        _replace_pending_promises(c)
        for d in c.dues:
            if d.status == "open":
                # balance_paise is kept as the amount written off, for the record.
                d.status = "written_off"
                d.closed_at = now
        c.collection_status = "normal"

    db.commit()
    return row


def resolve_dispute(db: Session, c: Customer, note: str | None = None) -> CallOutcome:
    """Dispute sorted out (e.g. the bill was corrected): back to normal rules."""
    if c.collection_status != "disputed":
        raise OutcomeError("This customer isn't marked as disputed")
    c.collection_status = "normal"
    row = CallOutcome(
        customer=c, outcome="dispute_resolved", note=(note or "").strip() or None, balance_paise=customer_balance(c), created_at=clock.now()
    )
    db.add(row)
    db.commit()
    return row
