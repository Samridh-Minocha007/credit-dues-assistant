"""Converting between rupees (what people type) and paise (what we store)."""
from decimal import ROUND_HALF_UP, Decimal


def to_paise(rupees: Decimal) -> int:
    # Decimal, not float: Decimal("120.50") * 100 is exactly 12050.
    return int((rupees * 100).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def format_rupees(paise: int) -> str:
    """12050 -> "120.50", 50000 -> "500" (no trailing .00 for whole rupees)."""
    rupees, rem = divmod(paise, 100)
    return f"{rupees:,}" if rem == 0 else f"{rupees:,}.{rem:02d}"
