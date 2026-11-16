"""Rules that protect customers from being pestered.

This slice: quiet hours (no messages at night) and opt-out.
Slice 3 adds the monthly reminder cap.
"""
from datetime import datetime, time, timedelta


def _t(hhmm: str) -> time:
    h, m = hhmm.split(":")
    return time(int(h), int(m))


def in_quiet_hours(moment: datetime, start: str, end: str) -> bool:
    """Quiet hours usually cross midnight (21:00 -> 08:00), so "inside" means
    after the start OR before the end. If they don't cross midnight
    (e.g. 13:00 -> 15:00), "inside" means after the start AND before the end."""
    s, e, t = _t(start), _t(end), moment.time()
    if s == e:
        return False  # no quiet hours configured
    if s < e:
        return s <= t < e
    return t >= s or t < e


def next_allowed_time(moment: datetime, start: str, end: str) -> datetime:
    """The earliest moment at or after `moment` that is outside quiet hours."""
    if not in_quiet_hours(moment, start, end):
        return moment
    end_today = datetime.combine(moment.date(), _t(end))
    # At 22:00, quiet hours end at 08:00 *tomorrow*; at 06:00, at 08:00 today.
    return end_today if end_today > moment else end_today + timedelta(days=1)
