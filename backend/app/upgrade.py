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
