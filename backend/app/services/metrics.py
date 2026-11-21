"""The numbers that tell us whether this works.

PRIMARY: share of dues recovered within 30 days.
  - Only bills at least 30 days old are counted ("mature"). A bill from
    last week can't be judged yet; counting it would make the number look
    worse than it is (and jump around as bills age).
  - A bill is "recovered" if its balance reached zero within 30 days of the
    credit sale (closed_at - created_at <= 30 days).
  - Written off = not recovered. Still open after 30 days = not recovered.
  - Shown two ways: by count of bills (the brief's metric) and by rupees
    (so one big unpaid bill isn't hidden by many small paid ones).

EXPERIMENT: the same primary metric split by the arm each bill was
created in (reply reading on vs off). Small groups are flagged: with only a
handful of bills, a difference is likely to be chance.

GUARDRAILS (things that must not get worse):
  - Opt-outs: customers who opted out, out of customers we've messaged.
    Deleted customers are counted separately (deletion also stops messages,
    but it's a different decision).
  - Stopped shopping: customers whose first reminder was at least 30 days
    ago and who haven't bought on credit since. A proxy: cash purchases
    aren't recorded, so someone may still shop and pay cash.

Also: promises kept (call vs reply), what the reply reader found, how old
the unpaid money is, and call outcomes.
"""
import json
from collections import Counter
from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import clock
from ..models import CallOutcome, Customer, Due, Message, Promise, Shop

WINDOW = timedelta(days=30)
SMALL_GROUP = 20  # below this many mature bills per arm, warn that differences may be chance
REMINDER_KINDS = ("weekly_reminder", "payday_reminder", "promise_followup")
AGE_BUCKETS = [(0, 7, "0-7 days"), (8, 14, "8-14 days"), (15, 30, "15-30 days"), (31, 60, "31-60 days"), (61, None, "Over 60 days")]


def _credit(d: Due) -> int:
    """How much went on credit for this bill (the bill minus what was paid at the counter)."""
    return d.bill_paise - d.paid_at_entry_paise


def _recovered(d: Due) -> bool:
    return d.status == "paid" and d.closed_at is not None and d.closed_at - d.created_at <= WINDOW


def _rate(part: int, whole: int) -> float | None:
    return round(part / whole, 4) if whole else None


def recovery(dues: list[Due], now: datetime) -> dict:
    mature = [d for d in dues if now - d.created_at >= WINDOW]
    recovered = [d for d in mature if _recovered(d)]
    return {
        "mature_bills": len(mature),
        "recovered_bills": len(recovered),
        "rate": _rate(len(recovered), len(mature)),
        "mature_paise": sum(_credit(d) for d in mature),
        "recovered_paise": sum(_credit(d) for d in recovered),
        "rate_by_amount": _rate(sum(_credit(d) for d in recovered), sum(_credit(d) for d in mature)),
        "written_off_bills": sum(1 for d in mature if d.status == "written_off"),
        "too_new_bills": len(dues) - len(mature),
    }


def compute(db: Session, shop: Shop) -> dict:
    now = clock.now()
    customers = list(db.scalars(select(Customer).where(Customer.shop_id == shop.id)))
    ids = [c.id for c in customers]
    dues = list(db.scalars(select(Due).where(Due.customer_id.in_(ids)))) if ids else []
    messages = list(db.scalars(select(Message).where(Message.customer_id.in_(ids)))) if ids else []
    promises = list(db.scalars(select(Promise).where(Promise.customer_id.in_(ids)))) if ids else []
    outcomes = list(db.scalars(select(CallOutcome).where(CallOutcome.customer_id.in_(ids)))) if ids else []

    # ---- experiment arms ----
    arms = {}
    for key, label in (("replies_on", "Reading replies: on"), ("baseline", "Reading replies: off")):
        r = recovery([d for d in dues if d.variant == key], now)
        r["label"] = label
        r["small_sample"] = r["mature_bills"] < SMALL_GROUP
        arms[key] = r
    untracked = sum(1 for d in dues if d.variant is None)

    # ---- guardrails ----
    messaged = {m.customer_id for m in messages if m.direction == "out" and m.status == "sent_sim"}
    live = [c for c in customers if c.deleted_at is None]
    opted_out = [c for c in live if c.opted_out_at is not None and c.id in messaged]

    first_reminder: dict[int, datetime] = {}
    for m in messages:
        if m.kind in REMINDER_KINDS and m.status == "sent_sim" and m.sent_at:
            if m.customer_id not in first_reminder or m.sent_at < first_reminder[m.customer_id]:
                first_reminder[m.customer_id] = m.sent_at
    eligible = [cid for cid, t in first_reminder.items() if now - t >= WINDOW]
    stopped = [cid for cid in eligible if not any(d.customer_id == cid and d.created_at > first_reminder[cid] for d in dues)]

    # ---- promises ----
    promise_stats = {}
    for source in ("call", "reply"):
        ps = [p for p in promises if p.source == source and p.status != "replaced"]
        decided = [p for p in ps if p.status in ("kept", "broken")]
        kept = sum(1 for p in ps if p.status == "kept")
        promise_stats[source] = {
            "total": len(ps),
            "kept": kept,
            "broken": sum(1 for p in ps if p.status == "broken"),
            "pending": sum(1 for p in ps if p.status == "pending"),
            "kept_rate": _rate(kept, len(decided)),  # out of promises whose date has passed
        }

    # ---- reply reader ----
    replies = [m for m in messages if m.direction == "in"]
    readings = [json.loads(m.parsed) for m in replies if m.parsed]
    intents = Counter(r["intent"] for r in readings)
    readers = Counter(r["parsed_by"] for r in readings)

    # ---- age of money still owed ----
    open_dues = [d for d in dues if d.status == "open"]
    buckets = []
    for lo, hi, label in AGE_BUCKETS:
        in_bucket = [d for d in open_dues if (now - d.created_at).days >= lo and (hi is None or (now - d.created_at).days <= hi)]
        buckets.append({"label": label, "bills": len(in_bucket), "paise": sum(d.balance_paise for d in in_bucket)})

    return {
        "as_of": now,
        "recovery": recovery(dues, now),
        "experiment": {"arms": [arms["replies_on"], arms["baseline"]], "untracked_bills": untracked, "small_group": SMALL_GROUP},
        "guardrails": {
            "messaged_customers": len(messaged),
            "opted_out": len(opted_out),
            "opt_out_rate": _rate(len(opted_out), len(messaged)),
            "deleted_customers": sum(1 for c in customers if c.deleted_at is not None),
            "reminded_30_days_ago": len(eligible),
            "stopped_buying_on_credit": len(stopped),
            "stopped_rate": _rate(len(stopped), len(eligible)),
        },
        "promises": promise_stats,
        "replies": {
            "received": len(replies),
            "read": len(readings),
            "promise": intents.get("promise", 0),
            "already_paid": intents.get("already_paid", 0),
            "other": intents.get("other", 0),
            "by_gemini": readers.get("gemini", 0),
            "by_rules": readers.get("rules", 0),
        },
        "outstanding": {"paise": sum(d.balance_paise for d in open_dues), "bills": len(open_dues), "buckets": buckets},
        "calls": dict(Counter(o.outcome for o in outcomes)),
    }
