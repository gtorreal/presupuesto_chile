from datetime import datetime, timezone

from sources.market_hours import is_chilean_market_open


# --- Chile uses CLST (UTC-3) ~Sep–Apr, CLT (UTC-4) ~Apr–Sep ---


def test_weekday_during_hours():
    # Wed Mar 11 2026, 12:30 UTC = 09:30 CLST (just opened)
    assert is_chilean_market_open(datetime(2026, 3, 11, 15, 0, tzinfo=timezone.utc)) is True


def test_weekday_before_open():
    # Wed Mar 11 2026, 12:00 UTC = 09:00 CLST (before 9:30)
    assert is_chilean_market_open(datetime(2026, 3, 11, 12, 0, tzinfo=timezone.utc)) is False


def test_weekday_after_close():
    # Wed Mar 11 2026, 19:30 UTC = 16:30 CLST (after 16:00)
    assert is_chilean_market_open(datetime(2026, 3, 11, 19, 30, tzinfo=timezone.utc)) is False


def test_saturday():
    assert is_chilean_market_open(datetime(2026, 3, 14, 15, 0, tzinfo=timezone.utc)) is False


def test_sunday():
    assert is_chilean_market_open(datetime(2026, 3, 15, 15, 0, tzinfo=timezone.utc)) is False


def test_exact_open_boundary():
    # 12:30 UTC = 09:30 CLST -> should be open (inclusive)
    assert is_chilean_market_open(datetime(2026, 3, 11, 12, 30, tzinfo=timezone.utc)) is True


def test_exact_close_boundary():
    # 19:00 UTC = 16:00 CLST -> should be closed (exclusive)
    assert is_chilean_market_open(datetime(2026, 3, 11, 19, 0, tzinfo=timezone.utc)) is False


# --- Holidays ---


def test_holiday_new_year():
    # Jan 1 2026 (Thu), 16:00 UTC = 13:00 CLST (within hours, but holiday)
    assert is_chilean_market_open(datetime(2026, 1, 1, 16, 0, tzinfo=timezone.utc)) is False


def test_holiday_labor_day():
    # May 1 2026 (Fri), 16:00 UTC = 12:00 CLT (within hours, but holiday)
    assert is_chilean_market_open(datetime(2026, 5, 1, 16, 0, tzinfo=timezone.utc)) is False


def test_holiday_independence_day():
    # Sep 18 2026 (Fri), 18:00 UTC = 15:00 CLST (within hours, but holiday)
    assert is_chilean_market_open(datetime(2026, 9, 18, 18, 0, tzinfo=timezone.utc)) is False


def test_default_utc_now():
    # Calling without argument should not raise
    result = is_chilean_market_open()
    assert isinstance(result, bool)
