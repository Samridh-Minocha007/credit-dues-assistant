"""A customer's statement: every bill and payment with a running balance,
like a page from the shop's notebook. Shared with the customer as a link,
it helps settle "I didn't buy that" disputes (the items are listed).
"""
from dataclasses import dataclass
from datetime import datetime

from ..models import Customer


@dataclass
class Line:
    at: datetime
    kind: str  # bill | payment | written_off
    text: str
    amount_paise: int  # + adds to what they owe, - reduces it
    balance_paise: int = 0


def statement_lines(c: Customer) -> list[Line]:
    lines: list[Line] = []
    for d in c.dues:
        items = ", ".join(" ".join(x for x in (i.description, i.qty) if x) for i in d.items)
        credit = d.bill_paise - d.paid_at_entry_paise
        lines.append(Line(d.created_at, "bill", items, credit))
        if d.status == "written_off" and d.closed_at:
            lines.append(Line(d.closed_at, "written_off", "", -d.balance_paise))
    for p in c.payments:
        lines.append(Line(p.paid_at, "payment", "UPI" if p.source == "upi" else "cash", -p.amount_paise))
    lines.sort(key=lambda l: (l.at, 0 if l.kind == "bill" else 1))
    running = 0
    for line in lines:
        running += line.amount_paise
        line.balance_paise = running
    return lines
