"""Customer control over their data and messages.

Opt-out: the customer replies STOP (or the shopkeeper taps "Stop messages").
No more reminders or notices. Replying START turns them back on.

Delete: on request, erase personal data. Owner's rule (docs/decisions.md):
keep the name, amounts and dates so the shopkeeper can settle any later
confusion; erase the phone number, item lists, message texts, replies and
learned UPI IDs. Without a phone number the app can never contact them
again.
"""
from sqlalchemy import delete, update
from sqlalchemy.orm import Session

from .. import clock
from ..models import Customer, CustomerUpiId, IncomingPayment, LineItem, Message, Promise, Shop
from . import templates
from .messaging import queue_message
from .payments import customer_balance
from .reply_parser import parse_reply

STOP_WORDS = {"stop", "unsubscribe", "band karo", "band", "बंद", "बंद करो"}
START_WORDS = {"start", "chalu karo", "शुरू"}


class PrivacyError(ValueError):
    pass


def opt_out(db: Session, customer: Customer) -> None:
    if customer.opted_out_at is None:
        customer.opted_out_at = clock.now()


def opt_in(db: Session, customer: Customer) -> None:
    if customer.deleted_at is not None:
        raise PrivacyError("This customer's data was deleted")
    customer.opted_out_at = None


def handle_reply(db: Session, shop: Shop, customer: Customer, text: str) -> Message:
    """A customer sent a message to the shop (simulated). Stored as an inbound
    message. STOP/START always work. Everything else is read for a promise
    ONLY when the shop has the experiment switched on; otherwise it's just
    stored (the baseline we compare against)."""
    now = clock.now()
    text = text.strip()
    inbound = Message(customer=customer, direction="in", kind="reply", body=text, status="received", sent_at=now, created_at=now)
    db.add(inbound)

    word = text.lower().strip(" .!")
    if word in STOP_WORDS and customer.opted_out_at is None:
        opt_out(db, customer)
        # A confirmation is the one message we send after an opt-out, as a
        # direct answer to theirs (hence force=True).
        queue_message(db, shop, customer, "opt_out_confirm", templates.opt_out_confirm(shop=shop.name, lang=shop.message_language), force=True)
    elif word in START_WORDS and customer.opted_out_at is not None:
        opt_in(db, customer)
        queue_message(db, shop, customer, "opt_in_confirm", templates.opt_in_confirm(shop=shop.name, lang=shop.message_language), force=True)
    elif word not in STOP_WORDS | START_WORDS and shop.reply_parsing_enabled and customer_balance(customer) > 0:
        read_promise(db, shop, customer, inbound, now)
    db.commit()
    return inbound


def read_promise(db: Session, shop: Shop, customer: Customer, inbound: Message, now) -> Promise | None:
    """The experiment: turn "kal dunga" into a promise with a date."""
    parsed = parse_reply(inbound.body, now.date())
    inbound.parsed = parsed.to_json()
    if not parsed.is_usable_promise:
        return None  # stored for the shopkeeper to read; nothing automatic
    for p in customer.promises:
        if p.status == "pending":
            p.status = "replaced"
    promise = Promise(
        customer=customer,
        promised_date=parsed.promised_date,
        source="reply",
        raw_text=inbound.body,
        parsed_by=parsed.parsed_by,
        confidence=parsed.confidence,
        status="pending",
        created_at=now,
    )
    db.add(promise)
    if customer.collection_status == "disputed":
        customer.collection_status = "normal"  # they've agreed to pay
    if customer.opted_out_at is None:
        # A direct answer to their message, so it goes out now, even at night.
        ack = templates.promise_ack(shop=shop.name, when=parsed.promised_date, lang=shop.message_language)
        queue_message(db, shop, customer, "promise_ack", ack, force=True)
    return promise


def delete_customer_data(db: Session, customer: Customer) -> None:
    if customer.deleted_at is not None:
        raise PrivacyError("Already deleted")
    now = clock.now()
    customer.deleted_at = now
    customer.opted_out_at = customer.opted_out_at or now
    # Phone must stay unique per shop, so replace it with a placeholder
    # instead of leaving it blank. "x000000012" can never be a real number.
    customer.phone = f"x{customer.id:09d}"
    customer.pay_token = None  # old payment links stop working

    due_ids = [d.id for d in customer.dues]
    if due_ids:
        db.execute(delete(LineItem).where(LineItem.due_id.in_(due_ids)))
    db.execute(delete(Message).where(Message.customer_id == customer.id))
    db.execute(delete(CustomerUpiId).where(CustomerUpiId.customer_id == customer.id))
    # Keep the payment amounts and dates, drop who-paid-from-where details.
    db.execute(
        update(IncomingPayment)
        .where(IncomingPayment.customer_id == customer.id)
        .values(payer_vpa="deleted", payer_name=None, note=None)
    )
    db.commit()
    db.expire(customer)
