from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import Customer
from ..schemas import CustomerDetail, CustomerSummary, DueOut
from ..services.customers import CustomerRow, list_customers
from ..services.shop import get_or_create_shop

router = APIRouter(prefix="/api/customers", tags=["customers"])


def _summary(r: CustomerRow) -> CustomerSummary:
    return CustomerSummary(
        id=r.customer.id,
        phone=r.customer.phone,
        name=r.customer.name,
        balance_paise=r.balance_paise,
        open_dues=r.open_dues,
        oldest_open_due_at=r.oldest_open_due_at,
        opted_out=r.customer.opted_out_at is not None,
    )


@router.get("", response_model=list[CustomerSummary])
def search_customers(q: str | None = Query(default=None, max_length=50), db: Session = Depends(get_db)):
    """Used for the list screen and for autocomplete while typing a phone number."""
    return [_summary(r) for r in list_customers(db, get_or_create_shop(db), q=q)]


@router.get("/{customer_id}", response_model=CustomerDetail)
def get_customer(customer_id: int, db: Session = Depends(get_db)):
    shop = get_or_create_shop(db)
    c = db.get(Customer, customer_id)
    if c is None or c.shop_id != shop.id:
        raise HTTPException(404, "Customer not found")
    open_dues = [d for d in c.dues if d.status == "open"]
    return CustomerDetail(
        id=c.id,
        phone=c.phone,
        name=c.name,
        balance_paise=sum(d.balance_paise for d in open_dues),
        open_dues=len(open_dues),
        oldest_open_due_at=min((d.created_at for d in open_dues), default=None),
        opted_out=c.opted_out_at is not None,
        consent_at=c.consent_at,
        consent_method=c.consent_method,
        created_at=c.created_at,
        dues=[DueOut.model_validate(d) for d in reversed(c.dues)],  # newest first
    )
