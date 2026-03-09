import logging
from datetime import datetime, timezone

import aiohttp

import config

from .base import DataSource, PriceTick

logger = logging.getLogger(__name__)

SYMBOLS = [
    ("DXY", "DXY"),
    ("HG", "COPPER"),
    ("VIX", "VIX"),
    ("TNX", "US10Y"),
    ("ECH", "ECH"),
]

QUOTE_URL = "https://api.twelvedata.com/price"


class TwelveDataSource(DataSource):
    """
    Twelve Data - Plan Pro $99/mo.
    Provides DXY, Copper (HG), VIX, US 10Y (TNX), ECH ETF.
    """

    name = "twelvedata"

    @property
    def is_enabled(self) -> bool:
        return bool(config.TWELVEDATA_API_KEY)

    async def fetch(self) -> list[PriceTick]:
        if not self.is_enabled:
            return []

        ticks = []
        now = datetime.now(timezone.utc)

        # Batch request: comma-separated symbols
        symbols_str = ",".join(s for s, _ in SYMBOLS)
        params = {
            "symbol": symbols_str,
            "apikey": config.TWELVEDATA_API_KEY,
        }

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(QUOTE_URL, params=params, timeout=aiohttp.ClientTimeout(total=15)) as resp:
                    resp.raise_for_status()
                    data = await resp.json()

            # Batch response is a dict keyed by symbol
            for api_symbol, symbol in SYMBOLS:
                item = data.get(api_symbol, {})
                if "price" not in item:
                    logger.warning("TwelveData: no price for %s", api_symbol)
                    continue

                price = float(item["price"])
                ticks.append(PriceTick(
                    time=now,
                    source=self.name,
                    symbol=symbol,
                    mid=price,
                    raw_json={api_symbol: item},
                ))
                logger.debug("TwelveData %s: %.4f", symbol, price)

        except Exception as e:
            logger.error("TwelveData fetch error: %s", e)

        return ticks
