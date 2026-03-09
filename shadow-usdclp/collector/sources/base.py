from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional
import logging
import math

logger = logging.getLogger(__name__)


@dataclass
class PriceTick:
    time: datetime
    source: str
    symbol: str
    mid: float
    bid: Optional[float] = None
    ask: Optional[float] = None
    volume: Optional[float] = None
    raw_json: dict = field(default_factory=dict)

    def __post_init__(self):
        if self.time.tzinfo is None:
            self.time = self.time.replace(tzinfo=timezone.utc)
        if not math.isfinite(self.mid) or self.mid <= 0:
            raise ValueError(f"Invalid mid price: {self.mid} (source={self.source}, symbol={self.symbol})")


class DataSource(ABC):
    """Abstract base class for all price data sources."""

    name: str = "base"

    @abstractmethod
    async def fetch(self) -> list[PriceTick]:
        """Fetch latest prices. Returns empty list on failure (graceful degradation)."""
        ...

    @property
    def is_enabled(self) -> bool:
        return True
