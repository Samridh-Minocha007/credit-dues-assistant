"""The prototype runs one shop. Real multi-shop sign-in is out of scope for now,
but every customer is already linked to a shop, so adding it later is easy."""
from sqlalchemy.orm import Session

from ..models import Shop

SHOP_ID = 1


def get_or_create_shop(db: Session) -> Shop:
    shop = db.get(Shop, SHOP_ID)
    if shop is None:
        shop = Shop(id=SHOP_ID)
        db.add(shop)
        db.commit()
    return shop
