"""A tiny stand-in for database migrations.

`create_all` makes missing *tables* but never adds *columns* to tables that
already exist. When a slice adds a column, an older dues.db needs it added
by hand. A real project would use Alembic for this; for a prototype, one
small function that is safe to run on every startup is easier to read.
"""
import secrets

from sqlalchemy import inspect, select, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from .models import Customer

# (table, column, SQL type) for every column added after a table first existed.
ADDED_COLUMNS = [
    ("customers", "pay_token", "VARCHAR(32)"),  # slice 2
    ("shops", "upi_id", "VARCHAR(100)"),  # slice 2
    ("shops", "scheduler_last_run_at", "DATETIME"),  # slice 3
    ("shops", "demo_clock_offset_s", "INTEGER NOT NULL DEFAULT 0"),  # slice 3
    ("customers", "deleted_at", "DATETIME"),  # slice 3
    ("customers", "collection_status", "VARCHAR(20) NOT NULL DEFAULT 'normal'"),  # slice 4
    ("promises", "parsed_by", "VARCHAR(10)"),  # slice 5
    ("promises", "confidence", "FLOAT"),  # slice 5
    ("messages", "parsed", "VARCHAR(300)"),  # slice 5
    ("dues", "variant", "VARCHAR(12)"),  # slice 6
    ("shops", "message_language", "VARCHAR(2) NOT NULL DEFAULT 'en'"),  # Hindi messages
    ("shops", "default_credit_limit_paise", "INTEGER"),  # credit limit
    ("customers", "credit_limit_paise", "INTEGER"),  # credit limit
    ("shops", "part_payment_nudge", "BOOLEAN NOT NULL DEFAULT FALSE"),  # nudge experiment
    ("shops", "payday_reminder", "BOOLEAN NOT NULL DEFAULT FALSE"),  # payday experiment
    ("shops", "owner_phone", "VARCHAR(10)"),  # pilot login
    ("shops", "pin_salt", "VARCHAR(32)"),  # pilot login
    ("shops", "pin_hash", "VARCHAR(64)"),  # pilot login
    ("shops", "failed_logins", "INTEGER NOT NULL DEFAULT 0"),  # pilot login
    ("shops", "locked_until", "TIMESTAMP"),  # pilot login
]


def upgrade(engine: Engine) -> None:
    insp = inspect(engine)
    with engine.begin() as conn:
        for table, column, sql_type in ADDED_COLUMNS:
            if column not in {c["name"] for c in insp.get_columns(table)}:
                conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {column} {sql_type}"))
        conn.execute(text("CREATE UNIQUE INDEX IF NOT EXISTS ix_customers_pay_token ON customers (pay_token)"))
        # Early slice-2 test payments were labelled "sim_link"; they're UPI payments now.
        conn.execute(text("UPDATE payments SET source = 'upi' WHERE source = 'sim_link'"))

    # Give old customers a payment link too.
    with Session(engine) as db:
        for c in db.scalars(select(Customer).where(Customer.pay_token.is_(None))):
            c.pay_token = new_pay_token()
        db.commit()


def new_pay_token() -> str:
    # ~64 bits of randomness, URL-safe, e.g. "q3VZ0n1x-Hs". Unguessable.
    return secrets.token_urlsafe(8)
