"""
Twelve Data source — replaces Yahoo Finance for macro/forex/commodity data.

Free tier: 800 requests/day, 8 requests/minute.
With 7 symbols polled every 15 minutes: ~672 req/day + USDCLP_SPOT only
during Chilean market hours (~26 req/day) = ~698 req/day (fits within limits).
On Chilean holidays, USDCLP_SPOT is skipped entirely, saving ~26 req/day.

API docs: https://twelvedata.com/docs
API key required (free registration at twelvedata.com).

Covers (free tier):
  - Forex:       USD/BRL, USD/MXN, USD/COP, USD/CLP (spot, market hours only)
  - Commodities: Copper (HG)
  - ETFs:        ECH (iShares Chile), VIXY (VIX proxy)

Not available on free tier:
  - DXY (not a tradeable symbol — use Frankfurter DXY_PROXY instead)
  - VIX (index, not tradeable — VIXY ETF used as proxy)
  - TNX/US10Y (requires Grow plan — covered by Yahoo Finance fallback)
"""

import asyncio
import logging
from datetime import datetime, timezone

import aiohttp

from .base import DataSource, PriceTick
from .market_hours import is_chilean_market_open

logger = logging.getLogger(__name__)

# Twelve Data symbol → our internal symbol name
# Forex uses "from/to" format; everything else is the ticker directly.
SYMBOLS: dict[str, str] = {
    "USD/BRL": "USDBRL",
    "USD/MXN": "USDMXN",
    "USD/COP": "USDCOP",
    "USD/CLP": "USDCLP_SPOT",
    "HG":      "COPPER",
    "ECH":     "ECH",
    "VIXY":    "VIX_PROXY",  # ProShares VIX Short-Term Futures ETF (tracks VIX)
}

# Symbols that should only be fetched during Chilean market hours
MARKET_HOURS_ONLY = {"USDCLP_SPOT"}

PRICE_URL = "https://api.twelvedata.com/price"


async def _fetch_one(
    session: aiohttp.ClientSession,
    td_symbol: str,
    api_key: str,
) -> float | None:
    """Fetch the current price for a single symbol. Returns None on failure."""
    params = {"symbol": td_symbol, "apikey": api_key}
    try:
        async with session.get(
            PRICE_URL,
            params=params,
            timeout=aiohttp.ClientTimeout(total=10),
        ) as resp:
            if resp.status == 429:
                logger.warning("Twelve Data 429 for %s — rate limited", td_symbol)
                return None
            resp.raise_for_status()
            data = await resp.json(content_type=None)

        # Error response: {"code": 400, "message": "...", "status": "error"}
        if data.get("status") == "error":
            logger.warning("Twelve Data error for %s: %s", td_symbol, data.get("message"))
            return None

        price_str = data.get("price")
        if price_str is None:
            logger.warning("Twelve Data: no price field for %s", td_symbol)
            return None

        return float(price_str)

    except Exception as e:
        logger.debug("Twelve Data error for %s: %s", td_symbol, e)
        return None


class TwelveDataSource(DataSource):
    """
    Market data via Twelve Data API.
    Covers forex (4, incl. USD/CLP spot), Copper, ECH, and VIXY (VIX proxy) on free tier.
    USD/CLP only fetched during Chilean market hours (Mon-Fri 9:30-16:00 CLT).
    DXY covered by Frankfurter; US10Y/VIX by Yahoo Finance fallback.
    Recommended poll interval: 900s (15 min) to stay within free tier limits.
    """

    name = "twelvedata"

    def __init__(self, api_key: str):
        self._api_key = api_key

    def update_api_key(self, key: str) -> None:
        self._api_key = key

    @property
    def is_enabled(self) -> bool:
        return bool(self._api_key)

    async def fetch(self) -> list[PriceTick]:
        if not self._api_key:
            logger.warning("twelvedata: no API key configured, skipping")
            return []

        now = datetime.now(timezone.utc)
        ticks: list[PriceTick] = []
        success = 0

        async with aiohttp.ClientSession() as session:
            for td_symbol, internal_symbol in SYMBOLS.items():
                if internal_symbol in MARKET_HOURS_ONLY and not is_chilean_market_open(now):
                    logger.debug("twelvedata: skipping %s (market closed)", internal_symbol)
                    continue

                price = await _fetch_one(session, td_symbol, self._api_key)

                if price is not None:
                    ticks.append(PriceTick(
                        time=now,
                        source=self.name,
                        symbol=internal_symbol,
                        mid=price,
                        raw_json={"symbol": td_symbol, "price": price},
                    ))
                    success += 1
                    logger.debug("twelvedata %s → %s: %.4f", td_symbol, internal_symbol, price)

                # Polite delay: 8 req/min limit → ~7.5s between requests to be safe
                # But since we fetch sequentially and each request takes ~1s,
                # a 1s pause keeps us well within limits.
                await asyncio.sleep(1.0)

        logger.info("twelvedata: fetched %d/%d symbols", success, len(SYMBOLS))
        return ticks
