"""Which shop is this request for?

Locally (the default), the app runs a single shop with id 1, so nothing
changes for development and demos.

In pilot mode (PILOT_MODE=1), each shop logs in, and the auth step for every
request (main.py) records the logged-in shop's id here. Everything else in
the app just calls get_or_create_shop(db) and gets the right shop, so no
screen or rule had to change to support many shops.

How it works: a "context variable" is a value that belongs to the current
request only, even when many requests run at the same time.
"""
from contextvars import ContextVar

from sqlalchemy.orm import Session

from ..models import Shop

SHOP_ID = 1  # the single shop used when login isn't required

current_shop_id: ContextVar[int | None] = ContextVar("current_shop_id", default=None)


def get_or_create_shop(db: Session) -> Shop:
    shop_id = current_shop_id.get()
    if shop_id is not None:
        return db.get(Shop, shop_id)
    shop = db.get(Shop, SHOP_ID)
    if shop is None:
        shop = Shop(id=SHOP_ID)
        db.add(shop)
        db.commit()
    return shop


def shop_of(db: Session, customer) -> Shop:
    """For customer-facing pages opened by link (no login): the customer's own shop."""
    return db.get(Shop, customer.shop_id)
