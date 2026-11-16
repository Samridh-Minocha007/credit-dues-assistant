"""Cleaning up phone numbers so the same person is never stored twice.

"+91 98765-43210", "098765 43210" and "9876543210" are all the same number.
We strip everything to the 10-digit mobile number.
"""
import re


class InvalidPhone(ValueError):
    pass


def normalize_phone(raw: str) -> str:
    digits = re.sub(r"\D", "", raw or "")
    if len(digits) == 12 and digits.startswith("91"):
        digits = digits[2:]
    elif len(digits) == 11 and digits.startswith("0"):
        digits = digits[1:]
    # Indian mobile numbers are 10 digits and start with 6, 7, 8 or 9.
    if not re.fullmatch(r"[6-9]\d{9}", digits):
        raise InvalidPhone("Enter a 10-digit mobile number")
    return digits
