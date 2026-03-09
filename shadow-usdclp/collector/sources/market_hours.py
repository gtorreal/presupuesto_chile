"""
Chilean stock exchange (Bolsa de Santiago) market hours utility.

Used to gate collection of USDCLP_SPOT — only fetch during trading hours
when the spot rate is actively updating.
"""

from datetime import datetime, timezone
from zoneinfo import ZoneInfo

SANTIAGO_TZ = ZoneInfo("America/Santiago")
MARKET_OPEN = (9, 30)
MARKET_CLOSE = (16, 0)


def is_chilean_market_open(utc_now=None):
    if utc_now is None:
        utc_now = datetime.now(timezone.utc)
    local = utc_now.astimezone(SANTIAGO_TZ)
    if local.weekday() > 4:
        return False
    t = (local.hour, local.minute)
    return MARKET_OPEN <= t < MARKET_CLOSE
