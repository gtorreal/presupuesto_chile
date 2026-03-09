"""
Yahoo Finance source using direct HTTP calls with proper crumb authentication.

Yahoo Finance API requires:
  1. Cookie from https://fc.yahoo.com (or finance.yahoo.com)
  2. Crumb from https://query2.finance.yahoo.com/v1/test/getcrumb
  3. Both included in subsequent API calls

This is exactly what the yfinance library does internally.
No API key required. Data has ~15min delay for some instruments.

Covers all external factors for free:
  - Forex:    USDBRL, USDMXN, USDCOP
  - Indices:  DXY, VIX, US10Y
  - Futures:  Copper (HG)
  - ETFs:     ECH
"""

import asyncio
import logging
import math
import time
from datetime import datetime, timezone

import aiohttp

from .base import DataSource, PriceTick

logger = logging.getLogger(__name__)

# Backoff state for 429 rate limiting
_backoff_until: float = 0.0          # time.monotonic() timestamp when backoff expires
_consecutive_429: int = 0            # count of consecutive all-429 cycles
_BACKOFF_BASE: int = 300             # base delay in seconds (= normal poll interval)
_BACKOFF_MAX: int = 3600             # max delay: 1 hour

# Yahoo ticker → our internal symbol name
TICKERS: dict[str, str] = {
    "USDBRL=X": "USDBRL",
    "USDMXN=X": "USDMXN",
    "USDCOP=X": "USDCOP",
    "DX-Y.NYB": "DXY",
    "HG=F":     "COPPER",
    "^VIX":     "VIX",
    "^TNX":     "US10Y",
    "ECH":      "ECH",
}

CHART_URL = "https://query2.finance.yahoo.com/v8/finance/chart/{ticker}"
CRUMB_URL = "https://query2.finance.yahoo.com/v1/test/getcrumb"
COOKIE_URL = "https://fc.yahoo.com"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json,text/plain,*/*",
    "Accept-Language": "en-US,en;q=0.9",
    "Origin": "https://finance.yahoo.com",
    "Referer": "https://finance.yahoo.com/",
}


class _CrumbResult:
    """Result of crumb fetch — distinguishes 429 from other failures."""
    __slots__ = ("crumb", "is_rate_limited")

    def __init__(self, crumb: str | None, is_rate_limited: bool = False):
        self.crumb = crumb
        self.is_rate_limited = is_rate_limited


async def _get_crumb(session: aiohttp.ClientSession) -> _CrumbResult:
    """Fetch Yahoo Finance crumb required for authenticated API calls."""
    try:
        # Step 1: get cookies
        await session.get(COOKIE_URL, headers=HEADERS, timeout=aiohttp.ClientTimeout(total=10))
        # Step 2: get crumb
        async with session.get(CRUMB_URL, headers=HEADERS, timeout=aiohttp.ClientTimeout(total=10)) as r:
            if r.status == 200:
                crumb = await r.text()
                crumb = crumb.strip()
                logger.debug("Got Yahoo crumb: %s", crumb[:8] + "...")
                return _CrumbResult(crumb)
            if r.status == 429:
                logger.warning("Crumb fetch returned HTTP 429 — rate limited")
                return _CrumbResult(None, is_rate_limited=True)
            logger.warning("Crumb fetch returned HTTP %d", r.status)
    except Exception as e:
        logger.warning("Could not get Yahoo crumb: %s", e)
    return _CrumbResult(None)


async def _fetch_one(
    session: aiohttp.ClientSession, yahoo_ticker: str, crumb: str | None
) -> tuple[float | None, list[tuple[datetime, float]]]:
    """Returns (current_price, historical_bars).
    historical_bars is a list of (timestamp, close) for the last 5 days of hourly bars.
    """
    url = CHART_URL.format(ticker=yahoo_ticker)
    params: dict = {"interval": "1h", "range": "5d"}
    if crumb:
        params["crumb"] = crumb

    try:
        async with session.get(
            url, params=params, headers=HEADERS, timeout=aiohttp.ClientTimeout(total=10)
        ) as resp:
            if resp.status == 429:
                logger.warning("Yahoo 429 for %s — will retry next cycle", yahoo_ticker)
                return None, []
            resp.raise_for_status()
            data = await resp.json(content_type=None)

        result = data.get("chart", {}).get("result")
        if not result:
            return None, []

        result_data = result[0]
        meta = result_data.get("meta", {})

        # Current price
        current_price = None
        price = meta.get("regularMarketPrice")
        if price is not None:
            f = float(price)
            current_price = f if not math.isnan(f) else None

        if current_price is None:
            closes = result_data.get("indicators", {}).get("quote", [{}])[0].get("close", [])
            closes = [c for c in closes if c is not None]
            current_price = float(closes[-1]) if closes else None

        # Historical hourly bars with actual timestamps
        timestamps = result_data.get("timestamp", [])
        closes_raw = result_data.get("indicators", {}).get("quote", [{}])[0].get("close", [])
        historical: list[tuple[datetime, float]] = []
        for ts, close in zip(timestamps, closes_raw):
            if close is not None and not math.isnan(close):
                bar_time = datetime.fromtimestamp(ts, tz=timezone.utc)
                historical.append((bar_time, float(close)))

        return current_price, historical

    except Exception as e:
        logger.debug("Yahoo Finance error for %s: %s", yahoo_ticker, e)
        return None, []


class YFinanceSource(DataSource):
    """
    Free data source via Yahoo Finance chart API with crumb authentication.
    Replaces Massive.com (forex) and Twelve Data (indices/futures/ETFs).
    Recommended poll interval: 300s.

    On first fetch, saves 5 days of hourly historical bars with real timestamps
    so the calculator can find factor prices at the last BEC close time.
    """

    name = "yfinance"
    _seeded: bool = False

    async def fetch(self) -> list[PriceTick]:
        global _backoff_until, _consecutive_429

        # Check backoff — skip this cycle if we're still in cooldown
        remaining = _backoff_until - time.monotonic()
        if remaining > 0:
            logger.info("yfinance: backoff active, skipping (%.0fs remaining)", remaining)
            return []

        now = datetime.now(timezone.utc)
        ticks = []
        seed_this_run = not YFinanceSource._seeded
        got_429 = 0
        attempted = 0

        async with aiohttp.ClientSession(cookie_jar=aiohttp.CookieJar()) as session:
            crumb_result = await _get_crumb(session)

            # If crumb fetch itself got 429, don't bother trying individual symbols
            if crumb_result.is_rate_limited:
                got_429 = len(TICKERS)
                attempted = len(TICKERS)
            else:
                for yahoo_ticker, symbol in TICKERS.items():
                    attempted += 1
                    price, historical = await _fetch_one(session, yahoo_ticker, crumb_result.crumb)

                    if price is None:
                        # _fetch_one logs 429 specifically; count them for backoff
                        got_429 += 1
                        logger.debug("yfinance: no data for %s (%s)", yahoo_ticker, symbol)
                    else:
                        ticks.append(PriceTick(
                            time=now,
                            source=self.name,
                            symbol=symbol,
                            mid=price,
                            raw_json={"ticker": yahoo_ticker, "price": price},
                        ))
                        logger.debug("yfinance %s (%s): %.4f", yahoo_ticker, symbol, price)

                    # On first run, also save historical hourly bars so get_price_at_bec_close
                    # can find factor values at the last BEC close (e.g. last Friday 3:30 PM).
                    if seed_this_run and historical:
                        for bar_time, bar_close in historical:
                            ticks.append(PriceTick(
                                time=bar_time,
                                source="yfinance_hist",
                                symbol=symbol,
                                mid=bar_close,
                                raw_json={"ticker": yahoo_ticker, "bar_close": bar_close, "seeded": True},
                            ))
                        logger.debug("yfinance seed %s: %d historical bars", symbol, len(historical))

                    # Polite delay between requests
                    await asyncio.sleep(1.5)

        # Backoff logic: if ALL symbols failed, increase backoff exponentially
        if attempted > 0 and got_429 >= attempted:
            _consecutive_429 += 1
            delay = min(_BACKOFF_BASE * (2 ** _consecutive_429), _BACKOFF_MAX)
            _backoff_until = time.monotonic() + delay
            logger.warning(
                "yfinance: all %d symbols got 429 (streak=%d) — backing off %ds",
                attempted, _consecutive_429, delay,
            )
        elif got_429 > 0:
            # Partial success — mild backoff but don't escalate
            _backoff_until = time.monotonic() + _BACKOFF_BASE
            logger.warning(
                "yfinance: %d/%d symbols got 429 — mild backoff %ds",
                got_429, attempted, _BACKOFF_BASE,
            )
        else:
            # Full success — reset backoff
            if _consecutive_429 > 0:
                logger.info("yfinance: recovered from 429 backoff (was streak=%d)", _consecutive_429)
            _consecutive_429 = 0
            _backoff_until = 0.0

        if seed_this_run:
            # NOTE: _seeded is set by collector/main.py AFTER save_ticks succeeds,
            # to avoid losing seed data if the DB write fails.
            hist_count = sum(1 for t in ticks if t.source == "yfinance_hist")
            logger.info("yfinance: seeded %d historical bars across all symbols", hist_count)

        logger.info("yfinance: fetched %d/%d symbols", sum(1 for t in ticks if t.source == "yfinance"), len(TICKERS))
        return ticks
