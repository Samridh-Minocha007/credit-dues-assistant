"""Reminder wording: checking it and filling it in.

The shopkeeper can edit the wording, but only with these placeholders. The
amount and the payment link must be present, otherwise the message is useless.
An opt-out line is always added at the end and cannot be removed, because
opt-out is a guardrail, not a preference.
"""
from string import Formatter

ALLOWED = {"name", "shop", "amount", "link"}
REQUIRED = {"amount", "link"}
OPT_OUT_LINE = "Reply STOP to stop these messages."


class InvalidTemplate(ValueError):
    pass


def validate_template(template: str) -> None:
    try:
        used = {field for _, field, _, _ in Formatter().parse(template) if field is not None}
    except ValueError as e:  # e.g. an unmatched "{"
        raise InvalidTemplate(f"Wording has a broken placeholder: {e}") from e
    unknown = used - ALLOWED
    if unknown:
        raise InvalidTemplate(f"Unknown placeholder(s): {', '.join(sorted(unknown))}")
    missing = REQUIRED - used
    if missing:
        raise InvalidTemplate(f"Wording must include: {', '.join('{' + m + '}' for m in sorted(missing))}")


def render(template: str, *, name: str | None, shop: str, amount: str, link: str) -> str:
    body = template.format(name=name or "ji", shop=shop, amount=amount, link=link)
    return f"{body} {OPT_OUT_LINE}"


# Fixed wording for transactional messages (a receipt for something that just
# happened at the counter). Unlike the weekly reminder, these are not
# editable: they only state facts, so there is nothing to approve.
def bill_notice(*, name: str | None, shop: str, credit: str, total: str, link: str | None) -> str:
    # No link if the shop hasn't added its UPI ID yet: customers pay at the counter.
    how = f"Pay anytime on UPI here: {link}" if link else "You can pay at the shop anytime."
    return (
        f"Namaste {name or 'ji'}, {shop} has noted Rs {credit} on credit today. "
        f"Total pending: Rs {total}. {how} {OPT_OUT_LINE}"
    )


def payment_receipt(*, name: str | None, shop: str, paid: str, remaining: str) -> str:
    rest = "Your account is fully cleared." if remaining == "0" else f"Remaining balance: Rs {remaining}."
    return f"Thank you {name or 'ji'}! {shop} received Rs {paid}. {rest}"
