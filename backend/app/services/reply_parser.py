"""Reading customer replies: is this a promise to pay, and by when?

Two readers, same output:

  1. Gemini (when GEMINI_API_KEY is set): handles free-form Hindi, Hinglish
     and English, e.g. "salary aate hi 1 tarikh ko bhej dunga".
  2. Rules (always available): keyword patterns for the common phrasings.
     Used when there's no API key, or when Gemini fails, times out or
     returns something that doesn't make sense.

Whatever Gemini says is checked like any untrusted input: the date must be
real, not in the past, and within 60 days, or we fall back to the rules.

Privacy: only the reply text and today's date are sent to Gemini. Never the
customer's name, phone number or amount.

Output intents:
  promise       "kal dunga", "will pay Friday"  -> promised_date set
  already_paid  "de diya", "paid yesterday"     -> shopkeeper should check
  other         anything else                   -> stored, nothing automatic
"""
import calendar
import json
import logging
import re
from dataclasses import dataclass
from datetime import date, timedelta

import httpx

from ..config import settings

MAX_DAYS = 60
MIN_CONFIDENCE = 0.6  # below this, don't act automatically

log = logging.getLogger(__name__)


@dataclass
class ParsedReply:
    intent: str  # promise | already_paid | other
    promised_date: date | None
    confidence: float
    parsed_by: str  # gemini | rules

    @property
    def is_usable_promise(self) -> bool:
        return self.intent == "promise" and self.promised_date is not None and self.confidence >= MIN_CONFIDENCE

    def to_json(self) -> str:
        return json.dumps(
            {
                "intent": self.intent,
                "promised_date": self.promised_date.isoformat() if self.promised_date else None,
                "confidence": round(self.confidence, 2),
                "parsed_by": self.parsed_by,
            }
        )


def parse_reply(text: str, today: date) -> ParsedReply:
    if settings.gemini_api_key:
        try:
            result = ask_gemini(text, today)
            if result is not None:
                return result
        except Exception:  # network error, bad JSON, quota... never break the reply flow
            log.warning("Gemini reply parsing failed; using rules", exc_info=True)
    return parse_with_rules(text, today)


def valid_promise_date(d: date | None, today: date) -> bool:
    return d is not None and today <= d <= today + timedelta(days=MAX_DAYS)


# ---------------------------------------------------------------------------
# Rules
# ---------------------------------------------------------------------------
# Weekday names. Short English forms that are also common words ("sun",
# "sat", "wed") are left out on purpose.
WEEKDAYS = {
    0: ["monday", "mon", "somvar", "somwar", "सोमवार"],
    1: ["tuesday", "tue", "tues", "mangalvar", "mangalwar", "मंगलवार"],
    2: ["wednesday", "budhvar", "budhwar", "बुधवार"],
    3: ["thursday", "thu", "thurs", "guruvar", "guruwar", "brihaspativar", "गुरुवार"],
    4: ["friday", "fri", "shukravar", "shukrawar", "शुक्रवार"],
    5: ["saturday", "shanivar", "shaniwar", "शनिवार"],
    6: ["sunday", "ravivar", "raviwar", "itvaar", "itwar", "रविवार"],
}
NEGATIVE = ["nahi", "nahin", "nhi", "not", "can't", "cannot", "won't", "wont", "नहीं", "nai"]
PAST_PAID = ["de diya", "diya", "bhej diya", "kar diya", "paid", "already", "ho gaya", "दे दिया", "भेज दिया"]
PAY_VERB = ["dunga", "dungi", "de dunga", "bhej", "pay", "payment", "paise", "dena", "denge", "transfer", "दूंगा", "दूँगा", "दे दूंगा"]


def _has(text: str, words: list[str]) -> bool:
    """Whole-word match for Latin words; plain substring for Devanagari
    (regex word boundaries don't work reliably with Hindi vowel signs)."""
    for w in words:
        if re.search(r"[ऀ-ॿ]", w):
            if w in text:
                return True
        elif re.search(rf"(?<![a-z]){re.escape(w)}(?![a-z])", text):
            return True
    return False


def _next_weekday(today: date, weekday: int) -> date:
    # Said on a Friday, "Friday" most likely means today.
    return today + timedelta(days=(weekday - today.weekday()) % 7)


def _next_day_of_month(today: date, day: int) -> date | None:
    if not 1 <= day <= 31:
        return None
    year, month = today.year, today.month
    for _ in range(3):
        last = calendar.monthrange(year, month)[1]
        candidate = date(year, month, min(day, last))
        if candidate >= today:
            return candidate
        month += 1
        if month == 13:
            year, month = year + 1, 1
    return None


def _find_date(t: str, today: date) -> date | None:
    if _has(t, ["parso", "parson", "parsoon", "day after tomorrow", "परसों"]):
        return today + timedelta(days=2)
    if _has(t, ["kal", "kl", "tomorrow", "tmrw", "tmr", "कल"]):
        return today + timedelta(days=1)
    if _has(t, ["aaj", "aj", "today", "abhi", "आज"]):
        return today
    if re.search(r"(agle|next)\s+(hafte|week)", t) or "अगले हफ्ते" in t:
        return today + timedelta(days=7)
    m = re.search(r"(\d{1,2})\s*(din|days?|दिन)", t)
    if m:
        return today + timedelta(days=int(m.group(1)))
    m = re.search(r"(\d{1,2})\s*(tarikh|tareekh|तारीख)", t) or re.search(r"(?<!\d)(\d{1,2})(st|nd|rd|th)(?![a-z])", t)
    if m:
        return _next_day_of_month(today, int(m.group(1)))
    if re.search(r"month\s*end|mahine\s*(ke|ka)?\s*(end|aakhir|akhir)", t):
        return date(today.year, today.month, calendar.monthrange(today.year, today.month)[1])
    for weekday, names in WEEKDAYS.items():
        if _has(t, names):
            return _next_weekday(today, weekday)
    return None


def parse_with_rules(text: str, today: date) -> ParsedReply:
    t = " ".join(text.lower().split())
    if _has(t, PAST_PAID):
        return ParsedReply("already_paid", None, 0.7, "rules")
    if _has(t, NEGATIVE):
        return ParsedReply("other", None, 0.6, "rules")  # "kal nahi de paunga" is not a promise
    d = _find_date(t, today)
    if not valid_promise_date(d, today):
        return ParsedReply("other", None, 0.5, "rules")
    # A date alone ("Friday ko") is probably a promise in reply to a dues
    # message; a date plus a paying word ("Friday ko de dunga") is clearer.
    return ParsedReply("promise", d, 0.85 if _has(t, PAY_VERB) else 0.65, "rules")


# ---------------------------------------------------------------------------
# Gemini
# ---------------------------------------------------------------------------
GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"

PROMPT = """You read short replies that customers of a small Indian grocery shop send after a polite
reminder about money they owe. Replies may be in Hindi, Hinglish (Hindi in Latin letters) or English.

Today is {today} ({weekday}).

Decide the intent:
- "promise": they say they will pay on or by a specific day (e.g. "kal dunga" = tomorrow,
  "parso" = day after tomorrow, "Friday ko", "5 tarikh", "next week").
- "already_paid": they say they have already paid.
- "other": anything else, including vague replies with no day ("jaldi dunga", "salary aane do")
  and refusals.
If it is a promise, give the date as YYYY-MM-DD. In replies about paying, "kal" means tomorrow.
Give your confidence from 0 to 1.

Reply: {text}"""

RESPONSE_SCHEMA = {
    "type": "OBJECT",
    "properties": {
        "intent": {"type": "STRING", "enum": ["promise", "already_paid", "other"]},
        "promised_date": {"type": "STRING", "nullable": True},
        "confidence": {"type": "NUMBER"},
    },
    "required": ["intent", "confidence"],
}


def ask_gemini(text: str, today: date) -> ParsedReply | None:
    """Returns None if Gemini's answer can't be trusted (then rules are used)."""
    body = {
        "contents": [{"parts": [{"text": PROMPT.format(today=today.isoformat(), weekday=today.strftime("%A"), text=text)}]}],
        "generationConfig": {"temperature": 0, "responseMimeType": "application/json", "responseSchema": RESPONSE_SCHEMA},
    }
    r = httpx.post(
        GEMINI_URL.format(model=settings.gemini_model),
        # Key in a header, not the URL, so it never shows up in logs.
        headers={"x-goog-api-key": settings.gemini_api_key},
        json=body,
        timeout=8,
    )
    r.raise_for_status()
    raw = r.json()["candidates"][0]["content"]["parts"][0]["text"]
    return _check_gemini_answer(json.loads(raw), today)


def _check_gemini_answer(data: dict, today: date) -> ParsedReply | None:
    intent = data.get("intent")
    if intent not in ("promise", "already_paid", "other"):
        return None
    try:
        confidence = max(0.0, min(1.0, float(data.get("confidence", 0))))
    except (TypeError, ValueError):
        return None
    promised = None
    if intent == "promise":
        try:
            promised = date.fromisoformat(data.get("promised_date") or "")
        except ValueError:
            return None
        if not valid_promise_date(promised, today):
            return None
    return ParsedReply(intent, promised, confidence, "gemini")
