"""Shapes of API requests and responses (validated automatically by FastAPI).

Convention: amounts coming IN are rupees (what the shopkeeper types, e.g.
"120.50"); amounts going OUT are integer paise with a `_paise` suffix, so
there is never any doubt which unit a number is in.
"""
import re
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, field_validator

HHMM = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")
Rupees = Decimal  # alias for readability


# ---------- settings ----------
class SettingsOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    name: str
    reminder_day: int
    reminder_time: str
    message_template: str
    settings_approved_at: datetime | None
    escalation_days: int
    escalation_amount_paise: int
    escalation_min_days: int
    quiet_start: str
    quiet_end: str
    max_reminders_per_month: int
    reply_parsing_enabled: bool
    # Extra fields computed by the router, not stored:
    approved: bool = False
    preview: str = ""


class SettingsUpdate(BaseModel):
    """Every field optional: send only what changed."""

    name: str | None = Field(default=None, min_length=1, max_length=100)
    reminder_day: int | None = Field(default=None, ge=0, le=6)
    reminder_time: str | None = None
    message_template: str | None = Field(default=None, min_length=10, max_length=300)
    escalation_days: int | None = Field(default=None, ge=1, le=365)
    escalation_amount: Rupees | None = Field(default=None, ge=0)
    escalation_min_days: int | None = Field(default=None, ge=1, le=365)
    quiet_start: str | None = None
    quiet_end: str | None = None
    max_reminders_per_month: int | None = Field(default=None, ge=1, le=8)
    reply_parsing_enabled: bool | None = None

    @field_validator("reminder_time", "quiet_start", "quiet_end")
    @classmethod
    def _hhmm(cls, v: str | None) -> str | None:
        if v is not None and not HHMM.match(v):
            raise ValueError("Use 24-hour HH:MM, e.g. 09:30")
        return v


# ---------- entries ----------
class ItemIn(BaseModel):
    description: str = Field(max_length=100)
    qty: str | None = Field(default=None, max_length=20)
    amount: Rupees | None = Field(default=None, ge=0, decimal_places=2)


class EntryIn(BaseModel):
    phone: str
    bill_amount: Rupees = Field(gt=0, max_digits=10, decimal_places=2)
    amount_paid: Rupees = Field(default=Decimal(0), ge=0, max_digits=10, decimal_places=2)
    name: str | None = Field(default=None, max_length=100)
    items: list[ItemIn] = Field(default_factory=list, max_length=50)


class ItemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    description: str
    qty: str | None
    amount_paise: int | None


class DueOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    bill_paise: int
    paid_at_entry_paise: int
    balance_paise: int
    status: str
    created_at: datetime
    closed_at: datetime | None
    items: list[ItemOut] = []


class CustomerSummary(BaseModel):
    id: int
    phone: str
    name: str | None
    balance_paise: int
    open_dues: int
    oldest_open_due_at: datetime | None
    opted_out: bool


class EntryOut(BaseModel):
    customer: CustomerSummary
    due: DueOut
    is_new_customer: bool


class CustomerDetail(CustomerSummary):
    consent_at: datetime
    consent_method: str
    created_at: datetime
    dues: list[DueOut]
