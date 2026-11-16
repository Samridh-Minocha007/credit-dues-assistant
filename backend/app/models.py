"""Database tables.

Money is stored as whole paise (integers): Rs 120.50 is stored as 12050.
Decimal fractions stored as floating point drift (0.1 + 0.2 != 0.3), which is
unacceptable for money. Integers never drift.

This slice adds shops, customers, dues and line_items. Payments, messages,
promises and call outcomes come in later slices.
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

    dues: Mapped[list["Due"]] = relationship(back_populates="customer", order_by="Due.created_at")


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
