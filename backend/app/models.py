"""Database tables.

Money is stored as whole paise (integers): Rs 120.50 is stored as 12050.
Decimal fractions stored as floating point drift (0.1 + 0.2 != 0.3), which is
unacceptable for money. Integers never drift.

Slice 1 added shops, customers, dues and line_items; slice 2 adds payments,
messages, incoming UPI payments and learned customer UPI IDs. Promises and call outcomes come in later slices.
"""
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base

DEFAULT_TEMPLATE = (
    "Namaste {name}, a friendly note from {shop}. "
    "Your pending balance is Rs {amount}. You can pay here: {link}. Thank you!"
)


class Shop(Base):
    """One row per shop. Holds the settings the shopkeeper approves ONCE."""

    __tablename__ = "shops"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100), default="My Shop")

    # Weekly reminder schedule. Python counts weekdays Monday=0 ... Sunday=6.
    reminder_day: Mapped[int] = mapped_column(Integer, default=6)
    reminder_time: Mapped[str] = mapped_column(String(5), default="10:00")  # "HH:MM", IST
    message_template: Mapped[str] = mapped_column(String(300), default=DEFAULT_TEMPLATE)
    # Set when the shopkeeper approves wording + schedule. Cleared if they edit
    # either, so automatic messages never go out with unapproved wording.
    settings_approved_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    # Escalation to "call this customer": oldest unpaid due >= escalation_days,
    # OR balance >= escalation_amount_paise and oldest due >= escalation_min_days.
    escalation_days: Mapped[int] = mapped_column(Integer, default=30)
    escalation_amount_paise: Mapped[int] = mapped_column(Integer, default=200_000)  # Rs 2,000
    escalation_min_days: Mapped[int] = mapped_column(Integer, default=14)

    # Guardrails
    quiet_start: Mapped[str] = mapped_column(String(5), default="21:00")
    quiet_end: Mapped[str] = mapped_column(String(5), default="08:00")
    max_reminders_per_month: Mapped[int] = mapped_column(Integer, default=4)

    # The A/B switch: read customer replies ("kal dunga") or not.
    reply_parsing_enabled: Mapped[bool] = mapped_column(Boolean, default=False)

    # The shop's existing UPI ID (the one behind its QR code), e.g. sharmastore@okaxis.
    # Customers pay straight to it; we never hold money.
    upi_id: Mapped[str | None] = mapped_column(String(100), nullable=True)

    # When the reminder timer last ran. Each run handles every weekly slot
    # since then, so nothing is missed if the server was off for a while
    # (or the demo clock jumped ahead).
    scheduler_last_run_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    # DEMO ONLY: how far the demo clock has been moved forward, in seconds.
    # Saved so a server restart doesn't snap the demo back to real time.
    demo_clock_offset_s: Mapped[int] = mapped_column(Integer, default=0)


class Customer(Base):
    __tablename__ = "customers"
    # The same phone can be a customer at two different shops, but only once per shop.
    __table_args__ = (UniqueConstraint("shop_id", "phone"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    shop_id: Mapped[int] = mapped_column(ForeignKey("shops.id"))
    phone: Mapped[str] = mapped_column(String(10), index=True)  # 10-digit Indian mobile
    name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    # Consent: the shopkeeper asks the customer for their number and tells them
    # about payment messages, so adding the number counts as consent. We still
    # record when and how, for audits.
    consent_at: Mapped[datetime] = mapped_column(DateTime)
    consent_method: Mapped[str] = mapped_column(String(40), default="given_to_shopkeeper")
    opted_out_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime)
    # Random, unguessable code in the customer's payment link (/pay/<token>).
    # That page opens the customer's UPI app pre-filled to pay the SHOP's own
    # UPI ID. (WhatsApp doesn't make upi:// links tappable, so we need a normal
    # web link in the message.) Random rather than the customer id, so nobody
    # can open someone else's page by changing a number in the URL.
    pay_token: Mapped[str | None] = mapped_column(String(32), unique=True, index=True, nullable=True)
    # Set when the customer's personal data is deleted on request. We keep
    # their name, amounts and dates (owner's rule, see docs/decisions.md) and
    # erase the phone number, items, messages and UPI IDs.
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    dues: Mapped[list["Due"]] = relationship(back_populates="customer", order_by="Due.created_at")
    payments: Mapped[list["Payment"]] = relationship(back_populates="customer", order_by="Payment.paid_at")
    messages: Mapped[list["Message"]] = relationship(back_populates="customer", order_by="Message.created_at")


class Due(Base):
    """One credit sale. A customer's total balance is the sum of their open dues."""

    __tablename__ = "dues"

    id: Mapped[int] = mapped_column(primary_key=True)
    customer_id: Mapped[int] = mapped_column(ForeignKey("customers.id"), index=True)
    bill_paise: Mapped[int] = mapped_column(Integer)
    paid_at_entry_paise: Mapped[int] = mapped_column(Integer, default=0)
    balance_paise: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(20), default="open")  # open | paid | written_off
    created_at: Mapped[datetime] = mapped_column(DateTime)
    # When the balance hit zero (or was written off). Primary metric:
    # recovered within 30 days  <=>  closed_at - created_at <= 30 days.
    closed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    customer: Mapped[Customer] = relationship(back_populates="dues")
    items: Mapped[list["LineItem"]] = relationship(back_populates="due", cascade="all, delete-orphan")


class LineItem(Base):
    """Optional itemised list for a due, to help settle disputes."""

    __tablename__ = "line_items"

    id: Mapped[int] = mapped_column(primary_key=True)
    due_id: Mapped[int] = mapped_column(ForeignKey("dues.id"), index=True)
    description: Mapped[str] = mapped_column(String(100))
    qty: Mapped[str | None] = mapped_column(String(20), nullable=True)  # free text: "2 kg", "1 pkt"
    amount_paise: Mapped[int | None] = mapped_column(Integer, nullable=True)

    due: Mapped[Due] = relationship(back_populates="items")


class Payment(Base):
    """Money received from a customer (simulated link or cash at the counter).

    A payment is for the customer's whole tab, not a specific bill. It is
    applied to the OLDEST open dues first, like crossing off the oldest lines
    in the notebook.
    """

    __tablename__ = "payments"

    id: Mapped[int] = mapped_column(primary_key=True)
    customer_id: Mapped[int] = mapped_column(ForeignKey("customers.id"), index=True)
    amount_paise: Mapped[int] = mapped_column(Integer)
    source: Mapped[str] = mapped_column(String(20))  # upi | cash
    paid_at: Mapped[datetime] = mapped_column(DateTime)

    customer: Mapped[Customer] = relationship(back_populates="payments")


class Message(Base):
    """Every message to or from a customer. Nothing is really sent: this table
    IS the simulated outbox.

    Messages blocked by a guardrail are stored too, with the reason in
    `status`. That shows the guardrails working, instead of messages silently
    vanishing.
    """

    __tablename__ = "messages"

    id: Mapped[int] = mapped_column(primary_key=True)
    customer_id: Mapped[int] = mapped_column(ForeignKey("customers.id"), index=True)
    direction: Mapped[str] = mapped_column(String(3), default="out")  # out | in
    # bill_notice | payment_receipt | weekly_reminder | promise_followup | reply
    kind: Mapped[str] = mapped_column(String(30))
    body: Mapped[str] = mapped_column(String(500))
    # sent_sim | scheduled (held for quiet hours) | blocked_opt_out | blocked_cap
    # (monthly limit reached) | cancelled_paid (paid before it went out) | received (inbound)
    status: Mapped[str] = mapped_column(String(30))
    scheduled_for: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime)

    customer: Mapped[Customer] = relationship(back_populates="messages")


class IncomingPayment(Base):
    """A UPI payment that landed in the shop's account, as the merchant app
    would report it: who paid (their UPI ID and name), how much, and the note.

    It is NOT linked to a customer when it arrives. Customers pay to the
    shop's single UPI ID, so the app has to work out who paid ("matching").
    Most UPI payments at a kirana are ordinary sales, not dues, so payments
    with no sign of being dues are left alone rather than flooding the
    shopkeeper with questions.
    """

    __tablename__ = "incoming_payments"

    id: Mapped[int] = mapped_column(primary_key=True)
    shop_id: Mapped[int] = mapped_column(ForeignKey("shops.id"))
    payer_vpa: Mapped[str] = mapped_column(String(100))  # payer's UPI ID, e.g. 9876543210@ybl
    payer_name: Mapped[str | None] = mapped_column(String(100), nullable=True)  # as their bank reports it
    amount_paise: Mapped[int] = mapped_column(Integer)
    note: Mapped[str | None] = mapped_column(String(100), nullable=True)
    received_at: Mapped[datetime] = mapped_column(DateTime)
    # matched_auto | needs_review | matched_confirmed | not_dues
    status: Mapped[str] = mapped_column(String(20))
    match_reason: Mapped[str] = mapped_column(String(200))  # plain-language "why", shown to the shopkeeper
    customer_id: Mapped[int | None] = mapped_column(ForeignKey("customers.id"), nullable=True)
    payment_id: Mapped[int | None] = mapped_column(ForeignKey("payments.id"), nullable=True)

    customer: Mapped[Customer | None] = relationship()


class CustomerUpiId(Base):
    """UPI IDs we've learned belong to a customer. After the shopkeeper
    confirms "yes, that was Ramesh" once, Ramesh's later payments from the
    same UPI ID are matched automatically. A customer can have several
    (e.g. their own and a family member's)."""

    __tablename__ = "customer_upi_ids"
    __table_args__ = (UniqueConstraint("shop_id", "vpa"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    shop_id: Mapped[int] = mapped_column(ForeignKey("shops.id"))
    customer_id: Mapped[int] = mapped_column(ForeignKey("customers.id"), index=True)
    vpa: Mapped[str] = mapped_column(String(100))
    learned_at: Mapped[datetime] = mapped_column(DateTime)
