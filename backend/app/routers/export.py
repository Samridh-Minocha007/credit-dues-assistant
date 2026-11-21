"""Download all the shop's data as a CSV file (opens in Excel / Google Sheets).

Shopkeepers won't trust an app with their khata unless they can take the
data out. One row per bill, payment or write-off, oldest first.
"""
import csv
import io

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import clock
from ..db import get_db
from ..models import Customer
from ..services.shop import get_or_create_shop
from ..services.statement import statement_lines

router = APIRouter(prefix="/api/export", tags=["export"])


@router.get("/ledger.csv")
def ledger_csv(db: Session = Depends(get_db)):
    shop = get_or_create_shop(db)
    out = io.StringIO()
    w = csv.writer(out)
    w.writerow(["date", "customer", "phone", "type", "details", "amount_rupees", "customer_balance_rupees"])
    rows = []
    for c in db.scalars(select(Customer).where(Customer.shop_id == shop.id)):
        phone = "" if c.deleted_at else c.phone
        for line in statement_lines(c):
            rows.append([line.at.strftime("%Y-%m-%d %H:%M"), c.name or "", phone, line.kind, line.text,
                         f"{line.amount_paise / 100:.2f}", f"{line.balance_paise / 100:.2f}"])
    rows.sort(key=lambda r: r[0])
    w.writerows(rows)
    filename = f"ledger-{clock.now():%Y-%m-%d}.csv"
    # "utf-8-sig" adds a marker so Excel shows Hindi names correctly.
    return StreamingResponse(
        iter([out.getvalue().encode("utf-8-sig")]),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
