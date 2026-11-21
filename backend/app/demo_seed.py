"""Generate a realistic demo shop: 120 days of credit, reminders, replies,
payments and calls, written to backend/demo.db (never the real dues.db).

    cd backend
    .venv/Scripts/python -m app.demo_seed            # 60 customers, 120 days
    .venv/Scripts/python -m app.demo_seed --customers 80 --days 150 --seed 3

Then start the server in demo mode (see README) to explore it.

How it works, and why it's credible: it does NOT write made-up rows. It
replays 120 days hour by hour through the app's REAL rules: entries go
through record_entry, payments through the UPI matching, replies through
the reply reader, reminders through the real timer, calls through the real
outcomes. Only the customers' behaviour is simulated, using simple,
stated assumptions (below). So the Results screen shows what our rules
produce under those assumptions, which is exactly how it must be described:
"in a simulation", never as real-world results.

Experiment: reply reading is OFF for the first half of the period and ON for
the second half (a before/after design, like switching it on in one shop).

Customer behaviour assumptions (all random, seeded so runs are repeatable):
  - each customer has a "reliability" (how likely they are to pay soon)
    and a shopping rate (how often they buy on credit)
  - chance of paying on a given day is low, higher in the 2 days after a
    reminder, and high on a day they promised (more so if reliable)
  - after a reminder, some customers reply: a promise ("kal dunga"),
    something vague ("jaldi dunga"), or "already paid"
  - about 1 in 100 reminders gets a STOP
  - the shopkeeper calls about half the people on the call list each day;
    most promise a date, a few dispute, a few are written off
"""
import argparse
import os
import random
from datetime import timedelta
from decimal import Decimal

os.environ.setdefault("DEMO_MODE", "1")  # must be set before the app's config is imported

from sqlalchemy import create_engine  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

from . import clock  # noqa: E402
from .config import BACKEND_DIR  # noqa: E402
from .db import Base  # noqa: E402
from .models import Customer  # noqa: E402
from .services.collections import call_list, record_outcome  # noqa: E402
from .services.entries import record_entry  # noqa: E402
from .models import IncomingPayment  # noqa: E402
from .services.matching import confirm, dismiss, handle_incoming  # noqa: E402
from .services.payments import customer_balance, record_payment  # noqa: E402
from .services.privacy import handle_reply  # noqa: E402
from .services.scheduler import run_scheduler  # noqa: E402
from .services.shop import get_or_create_shop  # noqa: E402
from .services.upi import payment_note  # noqa: E402

FIRST = ["Ramesh", "Sita", "Mohan", "Asha", "Bharat", "Kavita", "Suresh", "Pooja", "Rajesh", "Meena", "Anil", "Sunita",
         "Vijay", "Rekha", "Manoj", "Geeta", "Ravi", "Lata", "Deepak", "Neha", "Sanjay", "Usha", "Arjun", "Priya",
         "Imran", "Farah", "Harpreet", "Gurpreet", "Joseph", "Mary", "Vikram", "Anita", "Rahul", "Shalini", "Ajay", "Nisha"]
LAST = ["Kumar", "Devi", "Sharma", "Verma", "Gupta", "Singh", "Yadav", "Khan", "Patel", "Jain", "Mishra", "Thomas"]
PROMISES = ["kal dunga", "kal de dunga bhaiya", "parso de dunga", "will pay friday", "agle hafte", "3 din me de dunga",
            "monday ko pakka", "1 tarikh ko salary aayegi tab", "shukravar ko dunga"]
VAGUE = ["ok", "jaldi dunga", "thik hai", "haan bhai", "dekhta hoon"]
PAID_CLAIMS = ["de diya tha", "bhej diya"]


def _bill_amount(rng: random.Random) -> int:
    # Most kirana credit bills are small; a few are big monthly ones.
    rupees = rng.choice([rng.randint(40, 300)] * 6 + [rng.randint(300, 900)] * 3 + [rng.randint(900, 2500)])
    return max(20, round(rupees / 10) * 10)


DEMO_DB = BACKEND_DIR / "demo.db"


def generate(customers: int = 60, days: int = 120, seed: int = 7, verbose: bool = True, path=DEMO_DB) -> dict:
    # Safety: this deletes and rebuilds the file, so it must never be the real database.
    if path.name == "dues.db":
        raise ValueError("Refusing to overwrite the real database (dues.db)")
    rng = random.Random(seed)
    if path.exists():
        path.unlink()
    engine = create_engine(f"sqlite:///{path.as_posix()}", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)

    clock.reset()
    today = clock.now().replace(hour=0, minute=0, second=0)
    start = today - timedelta(days=days)
    switch_on = start + timedelta(days=days // 2)

    with Session(engine, expire_on_commit=False) as db:
        clock.set_now(start + timedelta(hours=9))
        shop = get_or_create_shop(db)
        shop.name = "Sharma General Store"
        shop.upi_id = "sharmageneral@okaxis"
        shop.reply_parsing_enabled = False
        shop.settings_approved_at = clock.now()
        db.commit()
        run_scheduler(db, shop)  # start the timer here

        people = []
        for i in range(customers):
            people.append({
                "phone": f"9{rng.randint(100000000, 999999999)}",
                "name": f"{rng.choice(FIRST)} {rng.choice(LAST)}" if rng.random() < 0.85 else None,
                "reliability": rng.uniform(0.15, 0.95),
                "visit_rate": rng.uniform(0.03, 0.2),
                "id": None,
            })

        counts = {"entries": 0, "payments": 0, "replies": 0, "calls": 0}
        day = start
        while day < today:
            if verbose and (day - start).days % 20 == 0:
                print(f"  simulating {day:%d %b}...")
            if day >= switch_on and not shop.reply_parsing_enabled:
                shop.reply_parsing_enabled = True
                db.commit()

            # 10:05 — the timer sends any reminder due this morning.
            clock.set_now(day + timedelta(hours=10, minutes=5))
            run_scheduler(db, shop)

            # 11:00 — the shopkeeper works through the call list.
            clock.set_now(day + timedelta(hours=11))
            for info in call_list(db, shop)["to_call"]:
                if rng.random() > 0.5:
                    continue
                roll = rng.random()
                c = info.customer
                if roll < 0.75:
                    record_outcome(db, shop, c, "promised_date", promised_date=(day + timedelta(days=rng.randint(1, 7))).date())
                elif roll < 0.88:
                    record_outcome(db, shop, c, "disputed", note="Says the amount is wrong")
                elif roll < 0.95:
                    record_outcome(db, shop, c, "written_off")
                counts["calls"] += 1

            # 12:00-20:00 — customers reply, pay and shop.
            for p in people:
                c = db.get(Customer, p["id"]) if p["id"] else None
                hour = rng.randint(12, 20)
                clock.set_now(day + timedelta(hours=hour, minutes=rng.randint(0, 59)))

                if c is not None and c.deleted_at is None:
                    reminded_recently = any(
                        m.kind in ("weekly_reminder", "promise_followup") and m.status == "sent_sim" and m.sent_at
                        and timedelta(0) <= clock.now() - m.sent_at <= timedelta(days=2)
                        for m in c.messages[-4:]
                    )
                    balance = customer_balance(c)

                    # Reply to a recent reminder?
                    if reminded_recently and balance > 0 and c.pay_token and rng.random() < 0.3:
                        roll = rng.random()
                        if roll < 0.03:  # 3% of replies, so about 1% of reminders, end in STOP
                            text = "STOP"
                        else:
                            text = rng.choice(PROMISES if roll < 0.6 else VAGUE if roll < 0.92 else PAID_CLAIMS)
                        handle_reply(db, shop, c, text)
                        counts["replies"] += 1

                    # Pay?
                    balance = customer_balance(c)
                    if balance > 0:
                        chance = 0.025 * p["reliability"]
                        if reminded_recently:
                            chance *= 4
                        promise = next((x for x in reversed(c.promises) if x.status == "pending"), None)
                        if promise and promise.promised_date == clock.now().date():
                            chance = 0.35 + 0.5 * p["reliability"]
                        if rng.random() < chance:
                            amount = balance if rng.random() < 0.7 else max(1000, (balance // 2) // 1000 * 1000)
                            amount = min(amount, balance)
                            if rng.random() < 0.6:  # UPI to the shop's own UPI ID
                                note = payment_note(c) if rng.random() < 0.8 else None
                                handle_incoming(db, shop, payer_vpa=f"{c.phone}@ybl", payer_name=(c.name or "CUSTOMER").upper(),
                                                amount_paise=amount, note=note)
                            else:
                                record_payment(db, shop, c, amount, source="cash")
                            counts["payments"] += 1

                # Buy on credit?
                if rng.random() < p["visit_rate"] and (c is None or (c.deleted_at is None and c.collection_status != "disputed")):
                    bill = _bill_amount(rng)
                    paid = 0 if rng.random() < 0.75 else round(bill * rng.uniform(0.2, 0.6) / 10) * 10
                    result = record_entry(db, shop, phone=p["phone"], bill_amount=Decimal(bill),
                                          amount_paid=Decimal(paid), name=p["name"])
                    p["id"] = result.customer.id
                    counts["entries"] += 1

            # Walk-in UPI sales from strangers (matching should leave these alone).
            if rng.random() < 0.6:
                clock.set_now(day + timedelta(hours=19))
                handle_incoming(db, shop, payer_vpa=f"walkin{rng.randint(1, 999)}@ybl", payer_name="WALK-IN",
                                amount_paise=rng.randint(30, 400) * 100, note=None)

            # 20:30 — the shopkeeper clears "payments to check": confirms most
            # suggestions, marks the rest as regular sales.
            clock.set_now(day + timedelta(hours=20, minutes=30))
            for inc in db.query(IncomingPayment).filter(IncomingPayment.status == "needs_review").all():
                target = db.get(Customer, inc.customer_id) if inc.customer_id else None
                if target is not None and customer_balance(target) > 0 and rng.random() < 0.85:
                    confirm(db, shop, inc, target)
                else:
                    dismiss(db, inc)

            day += timedelta(days=1)

        # Finish at real "now", with the timer caught up.
        clock.reset()
        shop.demo_clock_offset_s = 0
        run_scheduler(db, shop)
        db.commit()

    if verbose:
        print(f"Done: {customers} customers over {days} days -> {path}")
        print("  " + ", ".join(f"{v} {k}" for k, v in counts.items()))
    return counts


def main():
    ap = argparse.ArgumentParser(description="Generate the demo shop database (backend/demo.db).")
    ap.add_argument("--customers", type=int, default=60)
    ap.add_argument("--days", type=int, default=120)
    ap.add_argument("--seed", type=int, default=7, help="same seed, same data")
    args = ap.parse_args()
    generate(args.customers, args.days, args.seed)


if __name__ == "__main__":
    main()
