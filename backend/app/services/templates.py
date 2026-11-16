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
