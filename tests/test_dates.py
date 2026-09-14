"""Date parsing and helpers."""
from datetime import datetime
from utils import dates


def test_parse_various_formats():
    assert dates.parse_datetime("20 September 2026") == datetime(2026, 9, 20)
    assert dates.parse_datetime("27-Sep-2026") == datetime(2026, 9, 27)
    assert dates.parse_datetime("2026-09-20") == datetime(2026, 9, 20)
    assert dates.parse_datetime("20/09/2026") == datetime(2026, 9, 20)
    assert dates.parse_datetime("20-09-2026 15:30") == datetime(2026, 9, 20, 15, 30)


def test_parse_with_weekday_and_ordinal():
    assert dates.parse_datetime("Monday, 20th September 2026") == datetime(2026, 9, 20)


def test_parse_invalid():
    assert dates.parse_datetime("not a date") is None
    assert dates.parse_datetime("") is None


def test_normalize_date():
    assert dates.normalize_date("20 September 2026") == "2026-09-20"
    assert dates.normalize_date("20-09-2026 15:30") == "2026-09-20T15:30:00"


def test_days_until():
    future = dates.now_tz().replace(hour=0, minute=0, second=0, microsecond=0)
    from datetime import timedelta
    target = (future + timedelta(days=5)).strftime("%Y-%m-%d")
    assert dates.days_until(target) == 5
