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
from datetime import datetime, timezone

import aiohttp

from .base import DataSource, PriceTick

logger = logging.getLogger(__name__)

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


async def _get_crumb(session: aiohttp.ClientSession) -> str | None:
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
                return crumb
            logger.warning("Crumb fetch returned HTTP %d", r.status)
    except Exception as e:
        logger.warning("Could not get Yahoo crumb: %s", e)
    return None


async def _fetch_one(
    session: aiohttp.ClientSession, yahoo_ticker: str, crumb: str | None
) -> float | None:
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
                return None
            resp.raise_for_status()
            data = await resp.json(content_type=None)

        result = data.get("chart", {}).get("result")
        if not result:
            return None

        meta = result[0].get("meta", {})
        price = meta.get("regularMarketPrice")
        if price is not None:
            f = float(price)
            return f if not math.isnan(f) else None

        # Fallback: last close from quotes array
        closes = result[0].get("indicators", {}).get("quote", [{}])[0].get("close", [])
        closes = [c for c in closes if c is not None]
        return float(closes[-1]) if closes else None

    except Exception as e:
        logger.debug("Yahoo Finance error for %s: %s", yahoo_ticker, e)
        return None


class YFinanceSource(DataSource):
    """
    Free data source via Yahoo Finance chart API with crumb authentication.
    Replaces Massive.com (forex) and Twelve Data (indices/futures/ETFs).
    Recommended poll interval: 300s.
    """

    name = "yfinance"

    async def fetch(self) -> list[PriceTick]:
        now = datetime.now(timezone.utc)
        ticks = []

        async with aiohttp.ClientSession(cookie_jar=aiohttp.CookieJar()) as session:
            crumb = await _get_crumb(session)

            for yahoo_ticker, symbol in TICKERS.items():
                price = await _fetch_one(session, yahoo_ticker, crumb)

                if price is None:
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

                # Polite delay between requests
                await asyncio.sleep(1.5)

        logger.info("yfinance: fetched %d/%d symbols", len(ticks), len(TICKERS))
        return ticks
