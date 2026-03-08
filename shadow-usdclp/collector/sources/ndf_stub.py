"""
NDF Stub — USDCLP Non-Deliverable Forward (1-month)

This is the most valuable proxy for shadow USDCLP but requires LSEG Workspace
or a broker FIX feed (~$1,500-2,000/mo).

For now: reads from a manually-updated JSON file at /data/ndf_manual.json
Format: {"usdclp_ndf_1m": 955.50, "updated_at": "2025-01-15T18:00:00Z"}
"""

import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path

from .base import DataSource, PriceTick

logger = logging.getLogger(__name__)

NDF_DATA_FILE = Path(os.getenv("NDF_DATA_FILE", "/data/ndf_manual.json"))


class NdfDataSource(DataSource):
    """
    Stub for USDCLP NDF 1-month forward.
    Interface ready for production LSEG/FIX connection.
    Currently reads from a manually-updated JSON file.
    """

    name = "ndf_stub"

    async def fetch(self) -> list[PriceTick]:
        if not NDF_DATA_FILE.exists():
            return []

        try:
            data = json.loads(NDF_DATA_FILE.read_text())
            price = float(data["usdclp_ndf_1m"])
            updated_at_str = data.get("updated_at", "")

            try:
                tick_time = datetime.fromisoformat(updated_at_str.replace("Z", "+00:00"))
            except (ValueError, KeyError):
                tick_time = datetime.now(timezone.utc)

            logger.debug("NDF stub USDCLP 1M: %.2f", price)

            return [PriceTick(
                time=tick_time,
                source=self.name,
                symbol="USDCLP_NDF",
                mid=price,
                raw_json=data,
            )]
        except Exception as e:
            logger.error("NDF stub read error: %s", e)
            return []

    # ─── Interface for future live connection ───────────────────────────────────
    # When connecting to LSEG or FIX feed, implement:
    #   async def connect(self): ...
    #   async def subscribe(self, instruments: list[str]): ...
    #   async def on_price_update(self, msg): ...
