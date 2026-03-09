"""
BEC/Datatec Stub — Official USDCLP closing price from the Chilean stock exchange.

No public API exists. Three connection modes (configured via BEC_MODE env var):
  - "file"     : Read from a manually-updated CSV/JSON file (default)
  - "endpoint" : Fetch from a configurable HTTP endpoint (e.g., internal corredora API)
  - "scraper"  : Placeholder for a future web scraper

File format (bec_close.json):
  {"usdclp_close": 951.20, "date": "2025-01-15", "source": "manual"}

CSV format (bec_close.csv):
  date,close
  2025-01-15,951.20
  2025-01-14,948.50
"""

import asyncio
import csv
import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path

import aiohttp

from .base import DataSource, PriceTick

logger = logging.getLogger(__name__)

BEC_MODE = os.getenv("BEC_MODE", "file")
BEC_DATA_FILE = Path(os.getenv("BEC_DATA_FILE", "/data/bec_close.json"))
BEC_ENDPOINT_URL = os.getenv("BEC_ENDPOINT_URL", "")


class BecDataSource(DataSource):
    """
    Stub for official BEC/Datatec USDCLP closing price.
    """

    name = "bec_stub"

    async def fetch(self) -> list[PriceTick]:
        if BEC_MODE == "endpoint" and BEC_ENDPOINT_URL:
            return await self._fetch_endpoint()
        elif BEC_MODE == "scraper":
            logger.warning("BEC scraper mode not implemented yet")
            return []
        else:
            return await self._fetch_file()

    async def _fetch_file(self) -> list[PriceTick]:
        if not BEC_DATA_FILE.exists():
            return []

        try:
            suffix = BEC_DATA_FILE.suffix.lower()
            content = await asyncio.to_thread(BEC_DATA_FILE.read_text)

            if suffix == ".json":
                data = json.loads(content)
                price = float(data["usdclp_close"])
                date_str = data.get("date", "")
                try:
                    tick_time = datetime.strptime(date_str, "%Y-%m-%d").replace(tzinfo=timezone.utc)
                except ValueError:
                    tick_time = datetime.now(timezone.utc)
                raw = data

            elif suffix == ".csv":
                rows = list(csv.DictReader(content.splitlines()))
                if not rows:
                    return []
                latest = rows[-1]
                price = float(latest["close"])
                try:
                    tick_time = datetime.strptime(latest["date"], "%Y-%m-%d").replace(tzinfo=timezone.utc)
                except ValueError:
                    tick_time = datetime.now(timezone.utc)
                raw = {"date": latest["date"], "close": price}
            else:
                logger.error("BEC: unsupported file format %s", suffix)
                return []

            logger.debug("BEC close: %.2f", price)
            return [PriceTick(
                time=tick_time,
                source=self.name,
                symbol="USDCLP_BEC",
                mid=price,
                raw_json=raw,
            )]
        except Exception as e:
            logger.error("BEC file read error: %s", e)
            return []

    async def _fetch_endpoint(self) -> list[PriceTick]:
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(BEC_ENDPOINT_URL, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                    resp.raise_for_status()
                    data = await resp.json()

            price = float(data["usdclp_close"])
            date_str = data.get("date", "")
            try:
                tick_time = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
            except ValueError:
                tick_time = datetime.now(timezone.utc)

            return [PriceTick(
                time=tick_time,
                source=self.name,
                symbol="USDCLP_BEC",
                mid=price,
                raw_json=data,
            )]
        except Exception as e:
            logger.error("BEC endpoint fetch error: %s", e)
            return []
