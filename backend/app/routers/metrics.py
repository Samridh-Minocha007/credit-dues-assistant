"""Results: is the product working? Definitions are in services/metrics.py."""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..db import get_db
from ..services.metrics import compute
from ..services.shop import get_or_create_shop

router = APIRouter(prefix="/api/metrics", tags=["metrics"])


@router.get("")
def get_metrics(db: Session = Depends(get_db)):
    return compute(db, get_or_create_shop(db))
