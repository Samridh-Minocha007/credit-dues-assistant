"""Customer lists with their running balance (sum of open dues)."""
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from ..models import Customer, Due, Shop


@dataclass
class CustomerRow:
    customer: Customer
    balance_paise: int
    open_dues: int
    oldest_open_due_at: datetime | None


def list_customers(db: Session, shop: Shop, q: str | None = None, limit: int = 200) -> list[CustomerRow]:
    # A LEFT JOIN onto only the *open* dues, then sum per customer. Customers
    # with nothing open still appear, with a balance of 0.
    open_due = (Due.customer_id == Customer.id) & (Due.status == "open")
    stmt = (
        select(
            Customer,
            func.coalesce(func.sum(Due.balance_paise), 0),
            func.count(Due.id),
            func.min(Due.created_at),
        )
        .outerjoin(Due, open_due)
        .where(Customer.shop_id == shop.id)
        .group_by(Customer.id)
    )
    q = (q or "").strip()
    if q:
        digits = "".join(ch for ch in q if ch.isdigit())
        conditions = [Customer.name.ilike(f"%{q}%")]
        if digits:
            conditions.append(Customer.phone.contains(digits))
        stmt = stmt.where(or_(*conditions))
    # Biggest balance first: that's who the shopkeeper cares about.
    stmt = stmt.order_by(func.coalesce(func.sum(Due.balance_paise), 0).desc(), Customer.name).limit(limit)
    return [CustomerRow(c, int(bal), int(n), oldest) for c, bal, n, oldest in db.execute(stmt).all()]


def effective_limit(shop: Shop, c: Customer) -> int | None:
    """The customer's own limit if set, else the shop's default (None = no limit)."""
    return c.credit_limit_paise if c.credit_limit_paise is not None else shop.default_credit_limit_paise
