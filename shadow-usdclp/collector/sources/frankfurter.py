"""
Frankfurter API — Banco Central Europeo.

Free, official, no API key required.
Provides daily forex rates from ECB data.
URL: https://api.frankfurter.app

Covers:
  - USDBRL (via USD→BRL)
  - USDMXN (via USD→MXN)
  - USDCOP (via USD→COP)
  - DXY proxy: EUR/USD (EUR is ~57% of DXY basket)

Limitation: daily data (updates ~16:00 CET on business days).
Use as fallback/complement to Yahoo Finance.
"""

import logging
from datetime import datetime, timezone

import aiohttp

from .base import DataSource, PriceTick

logger = logging.getLogger(__name__)

URL = "https://api.frankfurter.app/latest"

# We request rates relative to USD so responses are USDXXX directly
TARGETS = ["BRL", "MXN", "COP", "EUR"]

# EUR/USD → DXY proxy (EUR ≈ 57.6% of DXY basket, inverse relationship)
# DXY_proxy = 1 / EURUSD  (not perfectly accurate, but directionally correct)


class FrankfurterSource(DataSource):
    """
    ECB forex rates via Frankfurter API.
    Free, official, no key required. Updates daily.
    Provides USDBRL, USDMXN, USDCOP and a DXY proxy.
    """

    name = "frankfurter"

    async def fetch(self) -> list[PriceTick]:
        now = datetime.now(timezone.utc)
        ticks = []

        params = {"from": "USD", "to": ",".join(TARGETS)}

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    URL,
                    params=params,
                    timeout=aiohttp.ClientTimeout(total=10),
                ) as resp:
                    resp.raise_for_status()
                    data = await resp.json(content_type=None)
        except Exception as e:
            logger.error("Frankfurter fetch error: %s", e)
            return []

        rates = data.get("rates", {})

        # USDBRL, USDMXN, USDCOP — direct from USD base
        for currency, symbol in [("BRL", "USDBRL"), ("MXN", "USDMXN"), ("COP", "USDCOP")]:
            rate = rates.get(currency)
            if rate is None:
                continue
            ticks.append(PriceTick(
                time=now,
                source=self.name,
                symbol=symbol,
                mid=float(rate),
                raw_json={"from": "USD", "to": currency, "rate": rate},
            ))
            logger.debug("Frankfurter USD/%s: %.4f", currency, rate)

        # DXY proxy from EUR/USD (inverted)
        eur_per_usd = rates.get("EUR")
        if eur_per_usd:
            # EUR/USD = 1 / (EUR per USD)  →  how many USD per EUR
            eurusd = 1.0 / float(eur_per_usd)
            # DXY proxy: inverse of EUR/USD scaled to typical DXY range
            # This is directionally correct, not numerically exact
            dxy_proxy = 1.0 / eurusd * 100  # rough scaling
            ticks.append(PriceTick(
                time=now,
                source=self.name,
                symbol="DXY_PROXY",  # distinct from real DXY
                mid=dxy_proxy,
                raw_json={"eurusd": eurusd, "dxy_proxy": dxy_proxy},
            ))
            logger.debug("Frankfurter EUR/USD: %.4f → DXY proxy: %.2f", eurusd, dxy_proxy)

        logger.info("Frankfurter: fetched %d ticks", len(ticks))
        return ticks
