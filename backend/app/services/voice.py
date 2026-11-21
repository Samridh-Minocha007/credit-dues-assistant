"""Voice entry: turn what the shopkeeper said into a filled-in form.

The phone's own speech recognition (in the browser) turns speech into text,
e.g. "Ramesh paanch sau udhaar do sau diye" or "Sita 450". This module reads
that text with simple rules:

  - amounts: digits ("500") or number words in Hindi/Hinglish/English
    ("paanch sau", "dedh hazaar", "dhai sau", "five hundred")
  - which amount was PAID: the one next to "diye/de diye/paid/cash"
    ("do sau diye", "paid 200"); the other one is the bill
  - who: a 10-digit phone number, or a name matched against existing
    customers ("Ramesh" -> Ramesh Kumar). Two Rameshes -> ask, don't guess.

It only fills the form. The shopkeeper always sees what was heard and
presses Save, so a misheard amount is caught before it's recorded.
Rules rather than an AI model on purpose: instant, works offline, and no
customer names leave the shop.
"""
import re
from dataclasses import dataclass, field

UNITS = {
    # Hindi / Hinglish
    "ek": 1, "do": 2, "teen": 3, "tin": 3, "char": 4, "chaar": 4, "paanch": 5, "panch": 5, "chhe": 6, "chhah": 6, "che": 6,
    "saat": 7, "sat": 7, "aath": 8, "ath": 8, "nau": 9, "das": 10, "gyarah": 11, "barah": 12, "baarah": 12, "terah": 13,
    "chaudah": 14, "pandrah": 15, "solah": 16, "satrah": 17, "atharah": 18, "unnis": 19, "bees": 20, "pachchis": 25,
    "pachis": 25, "pachees": 25, "tees": 30, "chalis": 40, "chaalis": 40, "pachas": 50, "pachaas": 50, "saath": 60,
    "sattar": 70, "assi": 80, "nabbe": 90,
    # Devanagari
    "एक": 1, "दो": 2, "तीन": 3, "चार": 4, "पांच": 5, "पाँच": 5, "छह": 6, "सात": 7, "आठ": 8, "नौ": 9, "दस": 10,
    "ग्यारह": 11, "बारह": 12, "पंद्रह": 15, "बीस": 20, "पच्चीस": 25, "तीस": 30, "चालीस": 40, "पचास": 50, "साठ": 60,
    "सत्तर": 70, "अस्सी": 80, "नब्बे": 90,
    # English
    "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10,
    "eleven": 11, "twelve": 12, "thirteen": 13, "fourteen": 14, "fifteen": 15, "sixteen": 16, "seventeen": 17,
    "eighteen": 18, "nineteen": 19, "twenty": 20, "thirty": 30, "forty": 40, "fifty": 50, "sixty": 60, "seventy": 70,
    "eighty": 80, "ninety": 90,
}
FRACTIONS = {"dedh": 1.5, "डेढ़": 1.5, "dhai": 2.5, "dhaai": 2.5, "ढाई": 2.5}
HUNDRED = {"sau", "so", "सौ", "hundred"}
THOUSAND = {"hazaar", "hazar", "hajar", "हज़ार", "हजार", "thousand"}
LAKH = {"lakh", "lac", "lakhs", "लाख"}
BIG = {**{w: 1000 for w in THOUSAND}, **{w: 100000 for w in LAKH}}
SAADHE = {"saadhe", "sadhe", "साढ़े"}  # "saadhe teen sau" = 350
PAID_AFTER = {"diye", "diya", "di", "paid", "jama", "दिए", "दिया"}  # "200 diye", "200 paid"
PAID_BEFORE = {"paid", "cash", "jama"}  # "paid 200"
PAID_WORDS = PAID_AFTER | PAID_BEFORE
FILLER = {"udhaar", "udhar", "credit", "rupaye", "rupees", "rs", "ka", "ki", "ke", "ko", "me", "mein", "aur", "and", "baaki",
          "baki", "likho", "likh", "do", "de", "उधार", "रुपये", "और"}


@dataclass
class VoiceResult:
    heard: str
    bill: float | None = None
    paid: float | None = None
    phone: str | None = None
    name: str | None = None  # name as spoken, if no customer matched
    customer_id: int | None = None
    candidates: list[dict] = field(default_factory=list)  # several customers match the name


def _tokens(text: str) -> list[str]:
    text = text.lower().replace("₹", " ")
    # Speech recognition writes big numbers with commas ("1,500", "1,25,000").
    # Join those first; any other comma just separates words.
    text = re.sub(r"(?<=\d),(?=\d)", "", text).replace(",", " ")
    return re.findall(r"[ऀ-ॿ]+|[a-z]+|\d+(?:\.\d+)?", text)


def _is_digits(tok: str) -> bool:
    return bool(re.fullmatch(r"\d+(\.\d+)?", tok))


def _unit_at(tokens: list[str], i: int) -> tuple[float, int] | None:
    """A single number word or digits at position i: (value, tokens used)."""
    tok = tokens[i]
    nxt = tokens[i + 1] if i + 1 < len(tokens) else ""
    if _is_digits(tok):
        return float(tok), 1
    if tok in SAADHE and nxt in UNITS:  # "saadhe teen" = 3.5
        return UNITS[nxt] + 0.5, 2
    if tok in FRACTIONS:
        return FRACTIONS[tok], 1
    if tok in UNITS:
        # "do" is also a common word ("likh do"): a number only before a multiplier.
        if tok == "do" and nxt not in HUNDRED and nxt not in BIG:
            return None
        return float(UNITS[tok]), 1
    return None


def _read_numbers(tokens: list[str]) -> list[tuple[float, int, int]]:
    """Find amounts the way people say them. Returns (value, first_index, last_index).

    Builds each number from left to right:
      "do hazaar teen sau"              2 x 1000 + 3 x 100       = 2300
      "one thousand two hundred fifty"  1000 + 200 + 50          = 1250
      "fifteen hundred"                 15 x 100                 = 1500
      "dedh lakh", "1.5 lakh"           1.5 x 100000             = 150000
      "ek sau pachaas"                  100 + 50                 = 150
    A new number starts when the words can't belong to the same one, e.g.
    "paanch sau, do sau diye" is 500 and 200 (two "hundreds" in a row), and
    digits are never glued to the next digits ("750 paid 250").
    """
    out, i = [], 0
    while i < len(tokens):
        if _unit_at(tokens, i) is None and not (tokens[i] in BIG or tokens[i] in HUNDRED - {"so"}):
            i += 1
            continue
        start = i
        total = 0.0  # the thousands / lakhs part
        group = 0.0  # the part below 1000
        group_has_hundred = False
        last_big = float("inf")  # e.g. after "hazaar", another "hazaar" means a new number
        last_plain = None  # last value added without a multiplier ("fifty", "500")
        last_plain_digits = False
        while i < len(tokens):
            tok = tokens[i]
            unit = _unit_at(tokens, i)
            if unit is None and (tok in BIG or (tok in HUNDRED and tok != "so")):
                unit = (1.0, 0)  # "hazaar" / "hundred" on its own means one of it
            if unit is None:
                break
            value, used = unit
            nxt = tokens[i + used] if i + used < len(tokens) else ""
            if nxt in HUNDRED:
                if group_has_hundred:
                    break  # a second "hundred": a new amount starts here
                if last_plain is not None:
                    # "twenty five hundred" = 25 x 100, but "500 do sau" is two amounts.
                    if last_plain_digits or group >= 100:
                        break
                    group = (group + value) * 100
                    group_has_hundred, last_plain = True, None
                    i += used + 1
                    continue
                group += value * 100
                group_has_hundred = True
                i += used + 1
                continue
            if nxt in BIG:
                mult = BIG[nxt]
                if mult >= last_big:
                    break
                total += (group + value) * mult
                group, group_has_hundred, last_big, last_plain = 0.0, False, mult, None
                i += used + 1
                continue
            if used == 0:
                break
            # A plain number. Join "twenty five", but not "500 300".
            if last_plain is not None:
                joinable = not _is_digits(tok) and last_plain % 10 == 0 and last_plain >= 20 and value < 10
                if not joinable:
                    break
            elif _is_digits(tok) and (group or total):
                # "2 hazaar 500" = 2500: digits right after "hazaar"/"lakh" fill the part below it.
                if not (total and not group and value < last_big):
                    break
            group += value
            last_plain, last_plain_digits = value, _is_digits(tok)
            i += used
        if i == start:
            i += 1
            continue
        out.append((total + group, start, i - 1))
    return out


def parse_voice(text: str, customers: list) -> VoiceResult:
    """customers: objects with .id, .name, .phone (the shop's customers)."""
    result = VoiceResult(heard=text.strip())
    tokens = _tokens(text)

    # A phone number said as digits (speech recognition often groups them: "98765 43210").
    digits = re.sub(r"\D", "", " ".join(t for t in tokens if t.isdigit()))
    m = re.search(r"[6-9]\d{9}", digits)
    used = set()
    if m:
        result.phone = m.group(0)
        used = {i for i, t in enumerate(tokens) if t.isdigit() and t in result.phone}

    numbers = [n for n in _read_numbers(tokens) if not (tokens[n[1]].isdigit() and n[1] in used)]
    def word_before(n):
        return tokens[n[1] - 1] if n[1] > 0 else ""

    def word_after(n):
        return tokens[n[2] + 1] if n[2] + 1 < len(tokens) else ""

    # Which amount was paid? "paid 250" (word before) wins over "750 paid" (word
    # after), so "750 paid 250" means bill 750, paid 250.
    paid = next((n for n in numbers if word_before(n) in PAID_BEFORE), None) or next(
        (n for n in numbers if word_after(n) in PAID_AFTER), None
    )
    if paid:
        result.paid = paid[0]
    bill = next((n for n in numbers if n is not paid), None)
    if bill:
        result.bill = bill[0]
    if result.bill is None and result.paid is not None:  # "500 diye" alone isn't a credit sale
        result.bill, result.paid = result.paid, None

    # Who: the words that aren't numbers or filler.
    number_words = set(UNITS) | set(FRACTIONS) | HUNDRED | THOUSAND | LAKH | SAADHE | PAID_WORDS
    words = [t for t in tokens if not t.isdigit() and t not in number_words and t not in FILLER and len(t) > 1]
    if result.phone:
        match = next((c for c in customers if c.phone == result.phone), None)
        if match:
            result.customer_id, result.name = match.id, match.name
    elif words:
        spoken = words[0]
        hits = [c for c in customers if c.name and c.name.lower().split()[0].startswith(spoken)]
        if len(hits) == 1:
            c = hits[0]
            result.customer_id, result.name, result.phone = c.id, c.name, c.phone
        else:
            result.name = spoken.capitalize()
            result.candidates = [{"id": c.id, "name": c.name, "phone": c.phone} for c in hits[:5]]
    return result
