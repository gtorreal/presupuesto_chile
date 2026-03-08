import logging
from datetime import datetime, timezone

import aiohttp

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
import config

from .base import DataSource, PriceTick

logger = logging.getLogger(__name__)

# Forex pairs to fetch from Massive/Polygon
TICKERS = [
    ("C:USDBRL", "USDBRL"),
    ("C:USDMXN", "USDMXN"),
    ("C:USDCOP", "USDCOP"),
]

BASE_URL = "https://api.polygon.io/v2/aggs/ticker/{ticker}/prev"


class MassiveSource(DataSource):
    """
    Massive.com (ex-Polygon.io) forex data.
    Plan Currencies: $49/mo. Provides USDBRL, USDMXN, USDCOP.
    """

    name = "massive"

    @property
    def is_enabled(self) -> bool:
        return bool(config.MASSIVE_API_KEY)

    async def fetch(self) -> list[PriceTick]:
        if not self.is_enabled:
            return []

        ticks = []
        params = {"apikey": config.MASSIVE_API_KEY, "adjusted": "true"}

        async with aiohttp.ClientSession() as session:
            for ticker, symbol in TICKERS:
                url = BASE_URL.format(ticker=ticker)
                try:
                    async with session.get(url, params=params, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                        resp.raise_for_status()
                        data = await resp.json()

                    results = data.get("results", [])
                    if not results:
                        logger.warning("Massive: no results for %s", ticker)
                        continue

                    r = results[0]
                    # t is Unix ms timestamp
                    tick_time = datetime.fromtimestamp(r["t"] / 1000, tz=timezone.utc)
                    mid = (r["o"] + r["c"]) / 2  # use open+close midpoint
                    volume = r.get("v")

                    ticks.append(PriceTick(
                        time=tick_time,
                        source=self.name,
                        symbol=symbol,
                        mid=mid,
                        bid=None,
                        ask=None,
                        volume=volume,
                        raw_json=data,
                    ))
                    logger.debug("Massive %s: %.4f", symbol, mid)
                except Exception as e:
                    logger.error("Massive fetch error for %s: %s", ticker, e)

        return ticks
