"""The ONLY way the app "sends" a message. Nothing ever leaves the machine.

Each message is written to the messages table (the simulated outbox) with a
status explaining what happened. To plug in a real WhatsApp/SMS provider
later, only this file would change.
"""
from sqlalchemy.orm import Session

from .. import clock
from ..config import settings
from ..models import Customer, Message, Shop
from .guardrails import in_quiet_hours, next_allowed_time


def pay_link(customer: Customer) -> str:
    return f"{settings.public_base_url}/pay/{customer.pay_token}"


def queue_message(db: Session, shop: Shop, customer: Customer, kind: str, body: str) -> Message:
    """Apply guardrails, then 'send' (simulated), schedule, or block. The
    caller commits."""
    now = clock.now()
    msg = Message(customer=customer, direction="out", kind=kind, body=body, created_at=now)

    if customer.opted_out_at is not None:
        msg.status = "blocked_opt_out"
    elif in_quiet_hours(now, shop.quiet_start, shop.quiet_end):
        # Don't drop it; hold it until morning. The scheduler (slice 3) sends
        # anything whose scheduled_for time has passed.
        msg.status = "scheduled"
        msg.scheduled_for = next_allowed_time(now, shop.quiet_start, shop.quiet_end)
    else:
        msg.status = "sent_sim"
        msg.sent_at = now

    db.add(msg)
    return msg
