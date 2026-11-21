"""The "Send on WhatsApp" button: the shopkeeper sends the message from their
own WhatsApp with one tap.

The app builds a WhatsApp "click to chat" link (wa.me) with the message
already written. WhatsApp opens; the shopkeeper presses send. Nothing is
sent automatically, so no WhatsApp Business account or message templates
are needed, which makes a real pilot possible today.

The same guardrails as automatic reminders apply to the button:
  - opted-out or deleted customers: no button
  - quiet hours: not until morning
  - the monthly limit: manual reminders count towards it
Each tap is logged as a message ("sent_manual"), so Activity, the monthly
limit and the metrics stay correct.
"""
from dataclasses import dataclass
from urllib.parse import quote

from sqlalchemy.orm import Session

from .. import clock
from ..models import Customer, Message, Shop
from . import templates
from .guardrails import in_quiet_hours, next_allowed_time
from .messaging import pay_link
from .money import format_rupees
from .payments import customer_balance
from .scheduler import _reminders_in_window, nudge_amount


@dataclass
class WhatsAppLink:
    allowed: bool
    reason: str | None
    text: str | None
    url: str | None


def whatsapp_url(phone: str, text: str) -> str:
    return f"https://wa.me/91{phone}?text={quote(text)}"


def reminder_link(db: Session, shop: Shop, c: Customer) -> WhatsAppLink:
    now = clock.now()
    if c.deleted_at is not None:
        return WhatsAppLink(False, "This customer's data was deleted", None, None)
    if c.opted_out_at is not None:
        return WhatsAppLink(False, "They opted out of messages", None, None)
    balance = customer_balance(c)
    if balance == 0:
        return WhatsAppLink(False, "Nothing is pending", None, None)
    if in_quiet_hours(now, shop.quiet_start, shop.quiet_end):
        when = next_allowed_time(now, shop.quiet_start, shop.quiet_end)
        return WhatsAppLink(False, f"Quiet hours: send after {when:%H:%M}", None, None)
    if _reminders_in_window(db, c, now) >= shop.max_reminders_per_month:
        return WhatsAppLink(False, "Monthly reminder limit reached for this customer", None, None)

    nudge = nudge_amount(balance) if shop.part_payment_nudge else None
    text = templates.render(
        shop.message_template,
        name=c.name,
        shop=shop.name,
        amount=format_rupees(balance),
        link=pay_link(c) if shop.upi_id else "(please pay at the shop)",
        lang=shop.message_language,
        nudge=format_rupees(nudge) if nudge else None,
    )
    # Logged so the monthly limit and Activity count it.
    db.add(Message(customer=c, direction="out", kind="manual_reminder", body=text, status="sent_manual", sent_at=now, created_at=now))
    db.commit()
    return WhatsAppLink(True, None, text, whatsapp_url(c.phone, text))
