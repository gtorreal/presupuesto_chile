"""
Shadow USDCLP - Data Collector Daemon

Two polling loops:
  - Fast (POLL_INTERVAL_SECONDS, default 30s):
      Buda.com, mindicador.cl, CMF, Frankfurter (forex ECB), NDF stub, BEC stub
  - Slow (YFINANCE_POLL_INTERVAL_SECONDS, default 300s):
      Twelve Data — USDBRL, USDMXN, USDCOP, DXY, VIX, Copper, US10Y, ECH
      Yahoo Finance — same symbols (fallback, may be rate-limited)
      (First source to return data wins via ON CONFLICT DO NOTHING)

Health endpoint: http://0.0.0.0:8001/health
"""

import asyncio
import json
import logging
import os
import signal
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, HTTPServer
from threading import Thread

import asyncpg

import config
import credential_store
from sources.base import PriceTick
from sources.buda import BudaSource
from sources.mindicador import MindicadorSource
from sources.cmf import CmfSource
from sources.frankfurter import FrankfurterSource
from sources.yfinance_source import YFinanceSource
from sources.twelvedata import TwelveDataSource
from sources.ndf_stub import NdfDataSource
from sources.bec_stub import BecDataSource

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%SZ",
)
logger = logging.getLogger("collector")

YFINANCE_POLL_INTERVAL = int(os.getenv("YFINANCE_POLL_INTERVAL_SECONDS", "300"))

FAST_SOURCES = [
    BudaSource(),
    MindicadorSource(),
    CmfSource(api_key=config.CMF_API_KEY),
    FrankfurterSource(),   # ECB forex: USDBRL, USDMXN, USDCOP, DXY proxy. Free, official.
    NdfDataSource(),
    BecDataSource(),
]

SLOW_SOURCES = [
    TwelveDataSource(api_key=config.TWELVEDATA_API_KEY),
    YFinanceSource(),  # fallback — may be rate-limited
]

ALL_SOURCES = FAST_SOURCES + SLOW_SOURCES


async def refresh_credentials(pool: asyncpg.Pool) -> None:
    """Refresh API keys from DB for all sources that use credentials."""
    try:
        creds = await credential_store.get_all_credentials(pool)
    except Exception as e:
        logger.warning("Failed to refresh credentials: %s", e)
        return

    # Update TwelveData
    td_key = creds.get(("twelvedata", "api_key"), "")
    for src in SLOW_SOURCES:
        if isinstance(src, TwelveDataSource) and td_key:
            src._api_key = td_key

    # Update CMF
    cmf_key = creds.get(("cmf", "api_key"), "")
    for src in FAST_SOURCES:
        if isinstance(src, CmfSource) and cmf_key:
            src._api_key = cmf_key

# State for health endpoint (shared between asyncio loop and HTTP thread)
import threading
_health_lock = threading.Lock()
_last_fast_fetch: datetime | None = None
_last_slow_fetch: datetime | None = None
_last_tick_count: int = 0


async def save_ticks(pool: asyncpg.Pool, ticks: list[PriceTick]) -> None:
    if not ticks:
        return

    rows = [
        (t.time, t.source, t.symbol, t.bid, t.ask, t.mid, t.volume, json.dumps(t.raw_json))
        for t in ticks
    ]

    async with pool.acquire() as conn:
        await conn.executemany(
            """
            INSERT INTO price_ticks (time, source, symbol, bid, ask, mid, volume, raw_json)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8::jsonb)
            ON CONFLICT (time, source, symbol) DO NOTHING
            """,
            rows,
        )


async def run_sources(pool: asyncpg.Pool, sources: list) -> int:
    """Fetch from a list of sources concurrently, save to DB. Returns tick count."""
    enabled = [s for s in sources if s.is_enabled]
    if not enabled:
        return 0

    results = await asyncio.gather(*[s.fetch() for s in enabled], return_exceptions=True)

    all_ticks: list[PriceTick] = []
    for src, result in zip(enabled, results):
        if isinstance(result, Exception):
            logger.error("Source %s raised exception: %s", src.name, result)
        else:
            all_ticks.extend(result)

    if all_ticks:
        await save_ticks(pool, all_ticks)
        # Mark yfinance as seeded only after successful DB write
        if not YFinanceSource._seeded and any(t.source == "yfinance_hist" for t in all_ticks):
            YFinanceSource._seeded = True

    return len(all_ticks)


async def get_config_interval(pool: asyncpg.Pool, key: str, default: int) -> int:
    """Read an interval from system_config, falling back to the default."""
    try:
        async with pool.acquire() as conn:
            row = await conn.fetchrow("SELECT value FROM system_config WHERE key = $1", key)
        return int(row["value"]) if row else default
    except Exception:
        return default


async def fast_loop(pool: asyncpg.Pool) -> None:
    global _last_fast_fetch, _last_tick_count

    while True:
        start = datetime.now(timezone.utc)
        interval = await get_config_interval(pool, "collector_fast_interval", config.POLL_INTERVAL_SECONDS)
        await refresh_credentials(pool)
        try:
            count = await run_sources(pool, FAST_SOURCES)
            with _health_lock:
                _last_tick_count = count
                _last_fast_fetch = datetime.now(timezone.utc)
            if count:
                logger.info("Fast sources: saved %d ticks", count)
        except Exception as e:
            logger.error("Fast loop DB error: %s", e)

        elapsed = (datetime.now(timezone.utc) - start).total_seconds()
        await asyncio.sleep(max(0, interval - elapsed))


async def slow_loop(pool: asyncpg.Pool) -> None:
    global _last_slow_fetch

    while True:
        start = datetime.now(timezone.utc)
        interval = await get_config_interval(pool, "collector_yfinance_interval", YFINANCE_POLL_INTERVAL)
        await refresh_credentials(pool)
        try:
            count = await run_sources(pool, SLOW_SOURCES)
            with _health_lock:
                _last_slow_fetch = datetime.now(timezone.utc)
            if count:
                logger.info("Slow sources (twelvedata+yfinance): saved %d ticks", count)
        except Exception as e:
            logger.error("Slow loop DB error: %s", e)

        elapsed = (datetime.now(timezone.utc) - start).total_seconds()
        await asyncio.sleep(max(0, interval - elapsed))


# ── Health endpoint ────────────────────────────────────────────────────────────

class HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/health":
            with _health_lock:
                fast = _last_fast_fetch.isoformat() if _last_fast_fetch else None
                slow = _last_slow_fetch.isoformat() if _last_slow_fetch else None
                ticks = _last_tick_count
            body = json.dumps({
                "status": "ok",
                "last_fast_fetch": fast,
                "last_slow_fetch": slow,
                "last_tick_count": ticks,
                "sources": [
                    {"name": s.name, "enabled": s.is_enabled, "loop": "fast"}
                    for s in FAST_SOURCES
                ] + [
                    {"name": s.name, "enabled": s.is_enabled, "loop": "slow"}
                    for s in SLOW_SOURCES
                ],
            }).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(body)
        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, *args):
        pass


def start_health_server():
    server = HTTPServer(("0.0.0.0", 8001), HealthHandler)
    Thread(target=server.serve_forever, daemon=True).start()
    logger.info("Health endpoint: http://0.0.0.0:8001/health")


# ── Entry point ────────────────────────────────────────────────────────────────

async def main():
    logger.info(
        "Starting collector — fast=%ds, yfinance=%ds",
        config.POLL_INTERVAL_SECONDS,
        YFINANCE_POLL_INTERVAL,
    )
    logger.info("Fast sources: %s", [s.name for s in FAST_SOURCES if s.is_enabled])
    logger.info("Slow sources: %s", [s.name for s in SLOW_SOURCES if s.is_enabled])

    pool = await asyncpg.create_pool(config.DATABASE_URL, min_size=2, max_size=5)

    # Seed credentials from env vars to DB (one-time), then load them
    await credential_store.seed_from_env(pool)
    await refresh_credentials(pool)

    # Skip yfinance historical re-seed if data already exists in the DB.
    # _seeded is in-memory and resets on every restart; this check makes it persistent.
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT 1 FROM price_ticks WHERE source = 'yfinance_hist'"
            " AND time > NOW() - INTERVAL '6 days' LIMIT 1"
        )
    if row:
        YFinanceSource._seeded = True
        logger.info("yfinance historical data already in DB — skipping re-seed on startup")

    start_health_server()

    loop = asyncio.get_running_loop()
    stop_event = asyncio.Event()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, stop_event.set)

    tasks = [
        asyncio.create_task(fast_loop(pool)),
        asyncio.create_task(slow_loop(pool)),
    ]

    await stop_event.wait()
    for t in tasks:
        t.cancel()
    await asyncio.gather(*tasks, return_exceptions=True)
    await pool.close()
    logger.info("Collector stopped")


if __name__ == "__main__":
    asyncio.run(main())
