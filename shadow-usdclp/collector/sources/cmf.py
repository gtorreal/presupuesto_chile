import logging
from datetime import datetime, timezone

import aiohttp

from .base import DataSource, PriceTick

logger = logging.getLogger(__name__)

URL = "https://api.cmfchile.cl/api-sbifv3/recursos_api/dolar"


class CmfSource(DataSource):
    """
    Dólar observado from CMF Chile API.
    Requires free API key from api.cmfchile.cl
    """

    name = "cmf"

    def __init__(self, api_key: str = ""):
        self._api_key = api_key

    def update_api_key(self, key: str) -> None:
        self._api_key = key

    @property
    def is_enabled(self) -> bool:
        return bool(self._api_key)

    async def fetch(self) -> list[PriceTick]:
        if not self.is_enabled:
            return []

        try:
            params = {"apikey": self._api_key, "formato": "json"}
            async with aiohttp.ClientSession() as session:
                async with session.get(URL, params=params, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                    resp.raise_for_status()
                    data = await resp.json(content_type=None)

            # Response: {"Dolares": [{"Valor": "950,50", "Fecha": "15-01-2025"}]}
            dolares = data.get("Dolares", [])
            if not dolares:
                return []

            latest = dolares[0]
            value_str = latest["Valor"].replace(".", "").replace(",", ".")
            value = float(value_str)
            fecha = latest["Fecha"]  # "DD-MM-YYYY"

            try:
                tick_time = datetime.strptime(fecha, "%d-%m-%Y").replace(tzinfo=timezone.utc)
            except ValueError:
                tick_time = datetime.now(timezone.utc)

            logger.debug("CMF USDCLP observado: %.2f (fecha: %s)", value, fecha)

            return [PriceTick(
                time=tick_time,
                source=self.name,
                symbol="USDCLP_OBS",
                mid=value,
                raw_json=data,
            )]
        except Exception as e:
            logger.error("CMF fetch error: %s", e)
            return []
