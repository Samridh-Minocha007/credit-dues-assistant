"""Building UPI payment links that pay the SHOP's own UPI ID.

A UPI link looks like:
    upi://pay?pa=sharmastore@okaxis&pn=Sharma%20Store&am=750.00&cu=INR&tn=Ramesh%20dues%20C12

  pa = payee address (the shop's UPI ID)     pn = payee name
  am = amount (pre-filled, customer can edit)  cu = currency
  tn = transaction note (pre-filled, customer can edit or delete)

Opening it on a phone launches GPay/PhonePe/Paytm with everything filled in;
the customer only enters their PIN. No per-customer link support is needed
from the merchant app: the money goes to the shop's normal UPI ID.

The note carries a short customer reference ("C12"). If it survives to the
shop's payment notification, we know exactly who paid.
"""
import re
from urllib.parse import quote

from ..models import Customer, Shop

UPI_ID = re.compile(r"^[\w.\-]{2,256}@[a-zA-Z][a-zA-Z0-9]{1,63}$")
REF = re.compile(r"\bC(\d{1,9})\b")


def customer_ref(customer: Customer) -> str:
    return f"C{customer.id}"


def payment_note(customer: Customer) -> str:
    who = (customer.name or "").split(" ")[0][:20] or "Customer"
    return f"{who} dues {customer_ref(customer)}"


def parse_ref(note: str | None) -> int | None:
    """"Ramesh dues C12" -> 12. Returns None if the note was cleared or edited away."""
    m = REF.search(note or "")
    return int(m.group(1)) if m else None


def upi_link(shop: Shop, customer: Customer, amount_paise: int) -> str:
    params = {
        "pa": shop.upi_id,
        "pn": shop.name,
        # UPI wants plain "750.00": no commas, always two decimals.
        "am": f"{amount_paise // 100}.{amount_paise % 100:02d}" if amount_paise else "",
        "cu": "INR",
        "tn": payment_note(customer),
    }
    return "upi://pay?" + "&".join(f"{k}={quote(v, safe='@.')}" for k, v in params.items() if v)
