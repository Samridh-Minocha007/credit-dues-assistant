"""The app's single source of "now".

Why not just call datetime.now() everywhere? Weekly reminders and a 30-day
escalation are impossible to demo if we have to wait real weeks. Every rule
asks this module for the time instead, and a dev endpoint (added later) can
move it forward, e.g. "jump 5 weeks", to show the whole loop in a minute.

All times are Indian Standard Time (the shop's local time), stored without a
timezone label. India has no daylight saving, so a fixed +05:30 offset is safe,
and "no messages after 9 pm" can be checked directly against these values.
"""
from datetime import datetime, timedelta, timezone

IST = timezone(timedelta(hours=5, minutes=30))

_offset = timedelta(0)


def now() -> datetime:
    return (datetime.now(IST) + _offset).replace(tzinfo=None, microsecond=0)


def advance(days: float = 0, hours: float = 0) -> datetime:
    global _offset
    _offset += timedelta(days=days, hours=hours)
    return now()


def set_now(when: datetime) -> datetime:
    """Jump to an exact moment (IST). Used by tests, e.g. "it is 10 pm"."""
    global _offset
    _offset = when - datetime.now(IST).replace(tzinfo=None)
    return now()


def offset_seconds() -> int:
    return int(_offset.total_seconds())


def set_offset(seconds: int) -> None:
    global _offset
    _offset = timedelta(seconds=seconds or 0)


def reset() -> None:
    global _offset
    _offset = timedelta(0)
