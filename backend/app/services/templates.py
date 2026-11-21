"""Message wording, in English or Hindi (the shop picks one in Settings).

The shopkeeper can edit the weekly reminder, but only with these
placeholders. The amount and the payment link must be present, otherwise the
message is useless. An opt-out line is always added at the end and cannot be
removed, because opt-out is a guardrail, not a preference.

Transactional messages (bill notice, receipt, confirmations) have fixed
wording: they only state facts, so there is nothing to approve.

Hindi is written in Devanagari. Amounts use the ₹ sign in Hindi and "Rs" in
English. "STOP"/"START" stay in Latin letters in both, since that's what
customers type (Hindi STOP words like "बंद" also work; see privacy.py).
"""
from datetime import date
from string import Formatter

ALLOWED = {"name", "shop", "amount", "link"}
REQUIRED = {"amount", "link"}
LANGUAGES = ("en", "hi")

OPT_OUT_LINE = {
    "en": "Reply STOP to stop these messages.",
    "hi": "ये संदेश बंद करने के लिए STOP लिखें।",
}

DEFAULT_TEMPLATES = {
    "en": "Namaste {name}, a friendly note from {shop}. Your pending balance is Rs {amount}. You can pay here: {link}. Thank you!",
    "hi": "नमस्ते {name}, {shop} की ओर से एक छोटा सा याद-संदेश। आपका बाकी ₹{amount} है। यहाँ भुगतान कर सकते हैं: {link} धन्यवाद!",
}
DEFAULT_TEMPLATE = DEFAULT_TEMPLATES["en"]  # kept for the database default

HI_WEEKDAYS = ["सोमवार", "मंगलवार", "बुधवार", "गुरुवार", "शुक्रवार", "शनिवार", "रविवार"]
HI_MONTHS = ["जनवरी", "फ़रवरी", "मार्च", "अप्रैल", "मई", "जून", "जुलाई", "अगस्त", "सितंबर", "अक्टूबर", "नवंबर", "दिसंबर"]


class InvalidTemplate(ValueError):
    pass


def _lang(lang: str | None) -> str:
    return lang if lang in LANGUAGES else "en"


def _who(name: str | None, lang: str) -> str:
    # "Ramesh ji" is polite in both; with no name, just "ji".
    if lang == "hi":
        return f"{name} जी" if name else "जी"
    return name or "ji"


def format_day(d: date, lang: str = "en") -> str:
    if _lang(lang) == "hi":
        return f"{HI_WEEKDAYS[d.weekday()]} {d.day} {HI_MONTHS[d.month - 1]}"
    return d.strftime("%A %d %B")


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


def render(
    template: str, *, name: str | None, shop: str, amount: str, link: str, lang: str = "en", nudge: str | None = None
) -> str:
    lang = _lang(lang)
    body = template.format(name=_who(name, lang), shop=shop, amount=amount, link=link)
    if nudge:
        body += " " + nudge_line(nudge, lang)
    return f"{body} {OPT_OUT_LINE[lang]}"


def nudge_line(amount: str, lang: str = "en") -> str:
    """The part-payment nudge: a smaller first step is easier to say yes to."""
    if _lang(lang) == "hi":
        return f"आज ₹{amount} भी दे दें तो बहुत मदद होगी।"
    return f"Even Rs {amount} today would help."


def bill_notice(*, name: str | None, shop: str, credit: str, total: str, link: str | None, lang: str = "en") -> str:
    lang = _lang(lang)
    who = _who(name, lang)
    if lang == "hi":
        how = f"UPI से कभी भी भुगतान करें: {link}" if link else "दुकान पर कभी भी भुगतान कर सकते हैं।"
        return f"नमस्ते {who}, {shop} में आज ₹{credit} उधार लिखा गया है। कुल बाकी: ₹{total}। {how} {OPT_OUT_LINE[lang]}"
    # No link if the shop hasn't added its UPI ID yet: customers pay at the counter.
    how = f"Pay anytime on UPI here: {link}" if link else "You can pay at the shop anytime."
    return f"Namaste {who}, {shop} has noted Rs {credit} on credit today. Total pending: Rs {total}. {how} {OPT_OUT_LINE[lang]}"


def payment_receipt(*, name: str | None, shop: str, paid: str, remaining: str, lang: str = "en") -> str:
    lang = _lang(lang)
    who = _who(name, lang)
    if lang == "hi":
        rest = "आपका पूरा हिसाब साफ़ हो गया है।" if remaining == "0" else f"बाकी: ₹{remaining}।"
        return f"धन्यवाद {who}! {shop} को ₹{paid} मिल गए। {rest}"
    rest = "Your account is fully cleared." if remaining == "0" else f"Remaining balance: Rs {remaining}."
    return f"Thank you {who}! {shop} received Rs {paid}. {rest}"


def opt_out_confirm(*, shop: str, lang: str = "en") -> str:
    if _lang(lang) == "hi":
        return f"अब {shop} से भुगतान के संदेश नहीं आएंगे। फिर से चालू करने के लिए START लिखें।"
    return f"You won't get any more payment messages from {shop}. Reply START if you change your mind."


def opt_in_confirm(*, shop: str, lang: str = "en") -> str:
    if _lang(lang) == "hi":
        return f"{shop} से भुगतान के संदेश फिर से चालू हो गए हैं। बंद करने के लिए कभी भी STOP लिखें।"
    return f"Payment messages from {shop} are back on. Reply STOP any time to stop them."


def promise_followup(*, name: str | None, shop: str, amount: str, link: str, lang: str = "en") -> str:
    lang = _lang(lang)
    who = _who(name, lang)
    if lang == "hi":
        return f"नमस्ते {who}, {shop} की ओर से याद दिला रहे हैं: आज भुगतान की बात हुई थी। बाकी: ₹{amount}। यहाँ भुगतान करें: {link} {OPT_OUT_LINE[lang]}"
    return (
        f"Namaste {who}, a gentle reminder from {shop} about the payment you planned for today. "
        f"Pending: Rs {amount}. Pay here: {link} {OPT_OUT_LINE[lang]}"
    )


def promise_ack(*, shop: str, when: date, lang: str = "en") -> str:
    if _lang(lang) == "hi":
        return f"धन्यवाद! {shop} ने नोट कर लिया है कि आप {format_day(when, 'hi')} तक भुगतान करेंगे। तब तक कोई याद-संदेश नहीं भेजेंगे।"
    return f"Thank you! {shop} has noted that you'll pay by {format_day(when)}. We won't send reminders until then."
