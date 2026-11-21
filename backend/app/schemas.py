"""Shapes of API requests and responses (validated automatically by FastAPI).

Convention: amounts coming IN are rupees (what the shopkeeper types, e.g.
"120.50"); amounts going OUT are integer paise with a `_paise` suffix, so
there is never any doubt which unit a number is in.
"""
import re
from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from .services.upi import UPI_ID

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
    upi_id: str | None
    message_language: str = "en"
    default_credit_limit_paise: int | None = None
    part_payment_nudge: bool = False
    payday_reminder: bool = False
    # Extra fields computed by the router, not stored:
    reply_reader: str = "rules"  # gemini (API key set) | rules
    demo_mode: bool = False  # running on the generated demo database
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
    upi_id: str | None = Field(default=None, max_length=100)
    message_language: str | None = Field(default=None, pattern="^(en|hi)$")
    default_credit_limit: Rupees | None = Field(default=None, ge=0)  # 0 = no limit
    part_payment_nudge: bool | None = None
    payday_reminder: bool | None = None

    @field_validator("upi_id")
    @classmethod
    def _upi(cls, v: str | None) -> str | None:
        if v is None:
            return v
        v = v.strip().lower()
        if not UPI_ID.match(v):
            raise ValueError("UPI ID looks like name@bank, e.g. sharmastore@okaxis")
        return v

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
    # Offline entries: a unique id from the phone, and when the sale really happened.
    client_ref: str | None = Field(default=None, max_length=40)
    recorded_at: datetime | None = None


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
    deleted: bool = False
    credit_limit_paise: int | None = None  # effective limit (own or shop default)
    own_credit_limit_paise: int | None = None  # set just for this customer


class MessageOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    customer_id: int
    direction: str
    kind: str
    body: str
    status: str
    scheduled_for: datetime | None
    sent_at: datetime | None
    created_at: datetime
    parsed: str | None = None


class OutboxRow(MessageOut):
    customer_name: str | None
    customer_phone: str


class EntryOut(BaseModel):
    customer: CustomerSummary
    due: DueOut
    is_new_customer: bool
    message: MessageOut
    over_limit: bool = False  # this sale took them past their credit limit


class PaymentIn(BaseModel):
    amount: Rupees = Field(gt=0, max_digits=10, decimal_places=2)


class PaymentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    amount_paise: int
    source: str
    paid_at: datetime


class PaymentResultOut(BaseModel):
    payment: PaymentOut
    balance_paise: int
    receipt: MessageOut

    @classmethod
    def build(cls, r) -> "PaymentResultOut":
        return cls(
            payment=PaymentOut.model_validate(r.payment),
            balance_paise=r.balance_paise,
            receipt=MessageOut.model_validate(r.receipt),
        )


class PayPageOut(BaseModel):
    """What the payment link page may show. Deliberately no phone number:
    anyone holding the link sees only the shop, a name and the amount."""

    shop_name: str
    shop_upi_id: str | None
    customer_name: str | None
    balance_paise: int
    upi_link: str | None  # opens the customer's UPI app, pre-filled
    note: str
    # Demo only: plausible defaults for the simulated UPI app's "paying from".
    demo_payer_vpa: str
    demo_payer_name: str


class BankNotificationIn(BaseModel):
    """SIMULATED: what the merchant app / bank tells us when money lands in the
    shop's UPI account. Note: no customer id. Matching has to work it out."""

    payer_vpa: str = Field(min_length=3, max_length=100)
    payee_vpa: str | None = Field(default=None, max_length=100)  # which shop was paid
    payer_name: str | None = Field(default=None, max_length=100)
    amount: Rupees = Field(gt=0, max_digits=10, decimal_places=2)
    note: str | None = Field(default=None, max_length=100)


class IncomingPaymentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    payer_vpa: str
    payer_name: str | None
    amount_paise: int
    note: str | None
    received_at: datetime
    status: str
    match_reason: str
    customer_id: int | None
    customer_name: str | None = None
    customer_balance_paise: int | None = None
    payment_id: int | None


class ConfirmIn(BaseModel):
    customer_id: int


class PhoneOut(BaseModel):
    """SIMULATED customer phone: the chat as the customer would see it."""

    shop_name: str
    customer_name: str | None
    pay_token: str
    messages: list[MessageOut]


class PromiseOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    promised_date: date
    source: str
    raw_text: str | None
    parsed_by: str | None = None
    confidence: float | None = None
    status: str
    followup_sent_at: datetime | None
    created_at: datetime


class CallOutcomeOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    outcome: str
    note: str | None
    balance_paise: int
    promise_id: int | None
    created_at: datetime


class CustomerDetail(CustomerSummary):
    consent_at: datetime
    consent_method: str
    created_at: datetime
    pay_link: str | None
    deleted_at: datetime | None
    dues: list[DueOut]
    payments: list[PaymentOut]
    messages: list[MessageOut]
    # reminders | promised | to_call | disputed | None (owes nothing)
    collection_state: str | None = None
    collection_reason: str | None = None
    promises: list[PromiseOut] = []
    call_outcomes: list[CallOutcomeOut] = []


class ReplyIn(BaseModel):
    """SIMULATED: a message the customer sends to the shop."""

    text: str = Field(min_length=1, max_length=300)


class ClockOut(BaseModel):
    now: datetime
    offset_seconds: int  # how far the demo clock is ahead of real time


class AdvanceIn(BaseModel):
    days: int = Field(default=0, ge=0, le=120)
    hours: int = Field(default=0, ge=0, le=72)


class RunOut(BaseModel):
    now: datetime
    delivered: int
    reminders_sent: int
    blocked_cap: int
    cancelled_paid: int
    promise_followups: int
    promises_broken: int
    slots: list[datetime]


class CallCardOut(BaseModel):
    """One customer on the call list (or waiting on a promise, or disputed)."""

    customer_id: int
    name: str | None
    phone: str
    balance_paise: int
    oldest_due_at: datetime
    oldest_age_days: int
    reason: str
    last_reminder_at: datetime | None
    latest_promise: PromiseOut | None


class CallListOut(BaseModel):
    to_call: list[CallCardOut]
    promised: list[CallCardOut]
    disputed: list[CallCardOut]


class OutcomeIn(BaseModel):
    outcome: str  # promised_date | disputed | written_off
    promised_date: date | None = None
    note: str | None = Field(default=None, max_length=300)


class ResolveIn(BaseModel):
    note: str | None = Field(default=None, max_length=300)


class CustomerUpdate(BaseModel):
    """Edit a customer's name or credit limit. Send credit_limit 0 to remove it."""

    name: str | None = Field(default=None, max_length=100)
    credit_limit: Rupees | None = Field(default=None, ge=0)


class VoiceIn(BaseModel):
    text: str = Field(min_length=1, max_length=300)


class VoiceOut(BaseModel):
    heard: str
    bill: float | None
    paid: float | None
    phone: str | None
    name: str | None
    customer_id: int | None
    candidates: list[dict]


class StatementLineOut(BaseModel):
    at: datetime
    kind: str
    text: str
    amount_paise: int
    balance_paise: int


class StatementOut(BaseModel):
    shop_name: str
    customer_name: str | None
    generated_at: datetime
    balance_paise: int
    lines: list[StatementLineOut]
