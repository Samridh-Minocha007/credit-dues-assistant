"""The reminder timer. Runs every minute in the background (and right after a
demo time jump). Each run does two jobs:

1. Deliver messages that were held for quiet hours, once their time comes.
2. Send the weekly reminder at the day/time the shopkeeper approved.

How it avoids missing or repeating reminders: the shop remembers when the
timer last ran. Each run walks through every weekly slot between then and
now, oldest first. If the server was off over a Sunday (or the demo clock
jumped three weeks), each missed Sunday is handled once, in order, with
the slot's own time. A slot is never handled twice because the next run
starts after it.

Rules for the weekly reminder (the guardrails):
  - only after the shopkeeper approved the wording and schedule
  - only customers who owe money, with a bill older than the slot
  - never opted-out or deleted customers
  - at most `max_reminders_per_month` in any 30 days; a reminder over the
    limit is stored as "blocked_cap" so the rule is visible
  - quiet hours apply (queue_message holds it until morning)
  - a held reminder is cancelled if the customer pays before it goes out
  - no automatic reminders for customers on the call list, with a promise
    that hasn't come due, or with a dispute (services/collections.py)

3. Promises: on the promised day, one polite follow-up at the reminder time.
   Paid in full -> "kept". Still owing the day after -> "broken", and the
   call rule applies again.
"""
from dataclasses import dataclass, field
from datetime import datetime, time, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import clock
from ..models import Customer, Message, Promise, Shop
from . import templates
from .messaging import pay_link, queue_message
from .collections import gets_automatic_reminders
from .money import format_rupees
from .payments import customer_balance

CAP_WINDOW = timedelta(days=30)
REMINDER_KINDS = ("weekly_reminder", "payday_reminder", "manual_reminder")  # all count towards the monthly limit
NUDGE_MIN_PAISE = 20000  # only suggest a part payment when Rs 200 or more is owed


def nudge_amount(balance_paise: int) -> int | None:
    """About half the balance, rounded down to Rs 50, at least Rs 50."""
    if balance_paise < NUDGE_MIN_PAISE:
        return None
    half = (balance_paise // 2) // 5000 * 5000
    return max(5000, half)


def payday_slots(shop: Shop, after: datetime, upto: datetime) -> list[datetime]:
    """The 1st of each month at the reminder time, with after < slot <= upto."""
    h, m = map(int, shop.reminder_time.split(":"))
    slot = datetime(after.year, after.month, 1, h, m)
    out = []
    while slot <= upto:
        if slot > after:
            out.append(slot)
        slot = datetime(slot.year + (slot.month == 12), slot.month % 12 + 1, 1, h, m)
    return out


@dataclass
class RunSummary:
    delivered: int = 0  # held messages that went out
    reminders_sent: int = 0  # includes ones now held for quiet hours
    blocked_cap: int = 0
    cancelled_paid: int = 0
    promise_followups: int = 0
    promises_broken: int = 0
    slots: list[datetime] = field(default_factory=list)


def weekly_slots(shop: Shop, after: datetime, upto: datetime) -> list[datetime]:
    """Every reminder time (e.g. Sundays 10:00) with after < slot <= upto."""
    h, m = map(int, shop.reminder_time.split(":"))
    first = datetime.combine(after.date(), time(h, m))
    first += timedelta(days=(shop.reminder_day - first.weekday()) % 7)
    while first <= after:
        first += timedelta(days=7)
    slots = []
    while first <= upto:
        slots.append(first)
        first += timedelta(days=7)
    return slots


def deliver_held(db: Session, shop: Shop, upto: datetime, summary: RunSummary) -> None:
    held = db.scalars(
        select(Message)
        .join(Customer)
        .where(Customer.shop_id == shop.id, Message.status == "scheduled", Message.scheduled_for <= upto)
        .order_by(Message.scheduled_for)
    )
    for msg in held:
        c = msg.customer
        if c.opted_out_at is not None or c.deleted_at is not None:
            msg.status = "blocked_opt_out"  # they opted out while it was waiting
        elif msg.kind in REMINDER_KINDS and customer_balance(c) == 0:
            msg.status = "cancelled_paid"  # they paid before it went out
            summary.cancelled_paid += 1
        else:
            msg.status = "sent_sim"
            msg.sent_at = msg.scheduled_for  # it would have gone out at that moment
            summary.delivered += 1


def _reminders_in_window(db: Session, customer: Customer, slot: datetime) -> int:
    return len(
        db.scalars(
            select(Message.id).where(
                Message.customer_id == customer.id,
                Message.kind.in_(REMINDER_KINDS),
                Message.status.in_(("sent_sim", "scheduled", "sent_manual")),
                Message.created_at > slot - CAP_WINDOW,
                Message.created_at <= slot,
            )
        ).all()
    )


def send_weekly(db: Session, shop: Shop, slot: datetime, summary: RunSummary, kind: str = "weekly_reminder") -> None:
    if shop.settings_approved_at is None or shop.settings_approved_at > slot:
        return  # not approved (yet) at this slot: no automatic reminders
    customers = db.scalars(
        select(Customer).where(Customer.shop_id == shop.id, Customer.deleted_at.is_(None), Customer.opted_out_at.is_(None))
    )
    for c in customers:
        open_dues = [d for d in c.dues if d.status == "open" and d.created_at < slot]
        if not open_dues:
            continue
        if not gets_automatic_reminders(shop, c, slot):
            continue  # on the call list, waiting on a promise, or disputed
        already = db.scalar(
            select(Message.id).where(
                Message.customer_id == c.id, Message.kind.in_(REMINDER_KINDS), Message.created_at >= slot.replace(hour=0, minute=0)
                , Message.created_at <= slot
            )
        )
        if already:
            continue  # already reminded at this slot or earlier that day (demo clock replay, or 1st falls on a Sunday)
        balance = customer_balance(c)
        body = templates.render(
            shop.message_template,
            name=c.name,
            shop=shop.name,
            amount=format_rupees(balance),
            link=pay_link(c) if shop.upi_id else "(please pay at the shop)",
            lang=shop.message_language,
            nudge=format_rupees(nudge_amount(balance)) if shop.part_payment_nudge and nudge_amount(balance) else None,
        )
        if _reminders_in_window(db, c, slot) >= shop.max_reminders_per_month:
            db.add(Message(customer=c, direction="out", kind=kind, body=body, status="blocked_cap", created_at=slot))
            summary.blocked_cap += 1
            continue
        queue_message(db, shop, c, kind, body, at=slot)
        summary.reminders_sent += 1


def process_promises(db: Session, shop: Shop, upto: datetime, summary: RunSummary) -> None:
    pending = db.scalars(
        select(Promise).join(Customer).where(Customer.shop_id == shop.id, Promise.status == "pending")
    )
    h, m = map(int, shop.reminder_time.split(":"))
    for p in pending:
        c = p.customer
        balance = customer_balance(c)
        if balance == 0:
            p.status = "kept"
            continue
        followup_at = datetime.combine(p.promised_date, time(h, m))
        if p.followup_sent_at is None and followup_at <= upto and c.collection_status != "disputed":
            body = templates.promise_followup(
                name=c.name, shop=shop.name, amount=format_rupees(balance),
                link=pay_link(c) if shop.upi_id else "(please pay at the shop)",
                lang=shop.message_language,
            )
            queue_message(db, shop, c, "promise_followup", body, at=followup_at)  # opt-out and quiet hours still apply
            p.followup_sent_at = followup_at
            summary.promise_followups += 1
        if upto.date() > p.promised_date:
            p.status = "broken"
            summary.promises_broken += 1


def run_scheduler(db: Session, shop: Shop) -> RunSummary:
    now = clock.now()
    summary = RunSummary()
    # First ever run: start from now. Don't send reminders for slots that
    # passed before the timer existed.
    last = shop.scheduler_last_run_at or now
    # Weekly slots, plus the 1st of each month if the payday experiment is on, in time order.
    slots = [(s, "weekly_reminder") for s in weekly_slots(shop, last, now)]
    if shop.payday_reminder:
        slots += [(s, "payday_reminder") for s in payday_slots(shop, last, now)]
    for slot, kind in sorted(slots):
        deliver_held(db, shop, slot, summary)  # morning messages before this slot first
        send_weekly(db, shop, slot, summary, kind)
        db.flush()  # so the next slot's monthly-limit count sees these reminders
        summary.slots.append(slot)
    process_promises(db, shop, now, summary)
    deliver_held(db, shop, now, summary)
    shop.scheduler_last_run_at = now
    db.commit()
    return summary
