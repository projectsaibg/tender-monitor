"""Date parsing and timezone helpers.

Tender portals present dates in many formats ("20 September 2026",
"27-Sep-2026", "2026/09/20", "20-09-2026 15:30"). :func:`parse_datetime`
tries a battery of formats and returns a naive ``datetime`` (local to the
portal). Everything is stored in the DB as ISO strings.
"""
from __future__ import annotations

import re
from datetime import datetime, date
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import config

_DATE_FORMATS = [
    "%Y-%m-%d", "%Y/%m/%d", "%d-%m-%Y", "%d/%m/%Y", "%d.%m.%Y",
    "%d %b %Y", "%d %B %Y", "%b %d %Y", "%B %d %Y",
    "%d-%b-%Y", "%d-%B-%Y", "%d %b, %Y", "%d %B, %Y",
    "%b %d, %Y", "%B %d, %Y", "%m/%d/%Y", "%Y%m%d",
]
_TIME_FORMATS = ["%H:%M:%S", "%H:%M", "%I:%M %p", "%I:%M:%S %p"]

_WEEKDAY_RE = re.compile(r"^(mon|tue|wed|thu|fri|sat|sun)[a-z]*[,\s]+", re.IGNORECASE)
_ORDINAL_RE = re.compile(r"(\d{1,2})(st|nd|rd|th)\b", re.IGNORECASE)


def get_timezone(name=None):
    """Return a ZoneInfo, falling back to the configured default then UTC."""
    for candidate in (name, config.DEFAULT_TIMEZONE, "UTC"):
        if not candidate:
            continue
        try:
            return ZoneInfo(candidate)
        except (ZoneInfoNotFoundError, ValueError, KeyError):
            continue
    return ZoneInfo("UTC")


def now_tz(name=None):
    return datetime.now(get_timezone(name))


def utcnow_iso():
    """Current UTC time as an ISO-8601 string (used for audit timestamps)."""
    return datetime.now(get_timezone("UTC")).replace(microsecond=0).isoformat()


def parse_datetime(text):
    """Best-effort parse of a human date/datetime string. Returns naive dt."""
    if not text:
        return None
    if isinstance(text, datetime):
        return text
    if isinstance(text, date):
        return datetime(text.year, text.month, text.day)

    raw = str(text).strip()
    if not raw:
        return None

    raw = _WEEKDAY_RE.sub("", raw).strip()
    raw = _ORDINAL_RE.sub(r"\1", raw)
    raw = raw.replace("  ", " ").strip(" .,")

    try:
        return datetime.fromisoformat(raw.replace("Z", "+00:00")).replace(tzinfo=None)
    except ValueError:
        pass

    for fmt in _DATE_FORMATS:
        try:
            return datetime.strptime(raw, fmt)
        except ValueError:
            continue

    parts = raw.split()
    for split_at in range(len(parts) - 1, 0, -1):
        date_part = " ".join(parts[:split_at])
        time_part = " ".join(parts[split_at:])
        for dfmt in _DATE_FORMATS:
            for tfmt in _TIME_FORMATS:
                try:
                    return datetime.strptime(f"{date_part} {time_part}", f"{dfmt} {tfmt}")
                except ValueError:
                    continue
    return None


def normalize_date(text):
    """Return a normalised ISO string for storage, or None if unparseable."""
    dt = parse_datetime(text)
    if dt is None:
        return None
    if dt.hour == 0 and dt.minute == 0 and dt.second == 0:
        return dt.strftime("%Y-%m-%d")
    return dt.strftime("%Y-%m-%dT%H:%M:%S")


def days_until(iso_or_text, tz_name=None):
    """Whole days from *today* (in tz) until the given date. Negative if past."""
    dt = parse_datetime(iso_or_text)
    if dt is None:
        return None
    today = now_tz(tz_name).date()
    return (dt.date() - today).days
