import logging
from datetime import datetime, timezone

import aiohttp

from .base import DataSource, PriceTick

logger = logging.getLogger(__name__)

URL = "https://mindicador.cl/api/dolar"


class MindicadorSource(DataSource):
    """
    Dólar observado oficial del Banco Central de Chile.
    Updates once per business day. Used as reference/anchor for BEC close.
    """

    name = "mindicador"

    async def fetch(self) -> list[PriceTick]:
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(URL, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                    resp.raise_for_status()
                    data = await resp.json(content_type=None)

            series = data.get("serie", [])
            if not series:
                logger.warning("mindicador: empty series")
                return []

            latest = series[0]
            value = float(latest["valor"])
            # fecha is in ISO format: "2025-01-15T03:00:00.000Z"
            # Mindicador publishes at 00:00 CLT (03:00 UTC), but the BEC close
            # actually happens at 15:30 CLT (19:30 UTC). Fix the timestamp.
            fecha_str = latest["fecha"]
            try:
                parsed = datetime.fromisoformat(fecha_str.replace("Z", "+00:00"))
                tick_time = parsed.replace(hour=19, minute=30, second=0, microsecond=0)
                # Never store a future timestamp
                now = datetime.now(timezone.utc)
                if tick_time > now:
                    tick_time = now
            except ValueError:
                tick_time = datetime.now(timezone.utc)

            logger.debug("mindicador USDCLP observado: %.2f (fecha: %s)", value, fecha_str)

            return [PriceTick(
                time=tick_time,
                source=self.name,
                symbol="USDCLP_OBS",
                mid=value,
                raw_json={"valor": value, "fecha": fecha_str},
            )]
        except Exception as e:
            logger.error("mindicador fetch error: %s", e)
            return []
