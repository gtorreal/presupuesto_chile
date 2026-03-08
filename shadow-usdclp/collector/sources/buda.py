import logging
from datetime import datetime, timezone

import aiohttp

from .base import DataSource, PriceTick

logger = logging.getLogger(__name__)

MARKETS = [
    ("usdc-clp", "USDCLP"),
    ("usdt-clp", "USDCLP_USDT"),
]

BASE_URL = "https://www.buda.com/api/v2/markets/{market}/ticker"


class BudaSource(DataSource):
    name = "buda"

    async def fetch(self) -> list[PriceTick]:
        ticks = []
        now = datetime.now(timezone.utc)

        async with aiohttp.ClientSession() as session:
            for market, symbol in MARKETS:
                url = BASE_URL.format(market=market)
                try:
                    async with session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                        resp.raise_for_status()
                        data = await resp.json()
                        ticker = data["ticker"]

                        last_price = float(ticker["last_price"][0])
                        bid = float(ticker["max_bid"][0]) if ticker.get("max_bid") and ticker["max_bid"][0] else None
                        ask = float(ticker["min_ask"][0]) if ticker.get("min_ask") and ticker["min_ask"][0] else None
                        volume = float(ticker["volume"][0]) if ticker.get("volume") else None

                        mid = last_price
                        if bid and ask:
                            mid = (bid + ask) / 2

                        ticks.append(PriceTick(
                            time=now,
                            source=self.name,
                            symbol=symbol,
                            mid=mid,
                            bid=bid,
                            ask=ask,
                            volume=volume,
                            raw_json=data,
                        ))
                        logger.debug("Buda %s: %.2f", symbol, mid)
                except Exception as e:
                    logger.error("Buda fetch error for %s: %s", market, e)

        return ticks
