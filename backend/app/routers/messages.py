from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from ..db import get_db
from ..models import Customer, Message
from ..schemas import OutboxRow
from ..services.shop import get_or_create_shop

router = APIRouter(prefix="/api/messages", tags=["messages"])


@router.get("", response_model=list[OutboxRow])
def outbox(
    customer_id: int | None = None,
    limit: int = Query(default=100, le=500),
    db: Session = Depends(get_db),
):
    """The simulated outbox: every message, newest first, including ones held
    for quiet hours or blocked by opt-out."""
    shop = get_or_create_shop(db)
    stmt = (
        select(Message)
        .join(Customer)
        .options(joinedload(Message.customer))
        .where(Customer.shop_id == shop.id)
        .order_by(Message.created_at.desc(), Message.id.desc())
        .limit(limit)
    )
    if customer_id is not None:
        stmt = stmt.where(Message.customer_id == customer_id)
    return [
        OutboxRow(
            **{k: getattr(m, k) for k in OutboxRow.model_fields if k not in ("customer_name", "customer_phone")},
            customer_name=m.customer.name,
            customer_phone=m.customer.phone,
        )
        for m in db.scalars(stmt)
    ]
