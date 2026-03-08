"""
Shadow USDCLP - Calculator Daemon

Runs two loops:
1. Shadow price loop: every SHADOW_CALC_INTERVAL_SECONDS
2. Correlation loop: once daily at 00:00 UTC

Exposes health endpoint on port 8002.
"""

import asyncio
import json
import logging
import os
import signal
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, HTTPServer
from threading import Thread

import asyncpg

from shadow_model import calculate_shadow, get_model_error_stddev, ShadowResult
from correlation_engine import run_correlations

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%SZ",
)
logger = logging.getLogger("calculator")

DATABASE_URL = os.environ["DATABASE_URL"]
SHADOW_CALC_INTERVAL = int(os.getenv("SHADOW_CALC_INTERVAL_SECONDS", "30"))
CONFIDENCE_K = float(os.getenv("CONFIDENCE_K", "2.0"))

_last_shadow: ShadowResult | None = None
_last_corr_run: datetime | None = None

# Sigma cache: recalculate at most once per hour to avoid band oscillation
SIGMA_UPDATE_INTERVAL = 3600
_cached_sigma: float | None = None
_sigma_last_updated: datetime | None = None


async def get_cached_sigma(pool: asyncpg.Pool) -> float:
    global _cached_sigma, _sigma_last_updated
    now = datetime.now(timezone.utc)
    if (
        _cached_sigma is None
        or _sigma_last_updated is None
        or (now - _sigma_last_updated).total_seconds() > SIGMA_UPDATE_INTERVAL
    ):
        _cached_sigma = await get_model_error_stddev(pool)
        _sigma_last_updated = now
        logger.info("Sigma recalculated: %.4f CLP", _cached_sigma)
    return _cached_sigma


async def save_shadow(pool: asyncpg.Pool, result: ShadowResult) -> None:
    async with pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO shadow_usdclp
                (time, shadow_price, confidence_low, confidence_high,
                 bec_last_close, bec_close_time, factors_used, factor_deltas, model_version)
            VALUES ($1,$2,$3,$4,$5,$6,$7::jsonb,$8::jsonb,$9)
            """,
            result.time,
            result.shadow_price,
            result.confidence_low,
            result.confidence_high,
            result.bec_last_close,
            result.bec_close_time,
            json.dumps(result.factors_used),
            json.dumps(result.factor_deltas),
            result.model_version,
        )


async def shadow_loop(pool: asyncpg.Pool) -> None:
    global _last_shadow

    while True:
        start = datetime.now(timezone.utc)
        try:
            sigma = await get_cached_sigma(pool)
            result = await calculate_shadow(pool, CONFIDENCE_K, sigma=sigma)
            if result:
                await save_shadow(pool, result)
                _last_shadow = result
                logger.info(
                    "Shadow USDCLP: %.2f [%.2f, %.2f] (BEC close: %.2f, %.1fh ago, %d factors)",
                    result.shadow_price,
                    result.confidence_low,
                    result.confidence_high,
                    result.bec_last_close,
                    (result.time - result.bec_close_time).total_seconds() / 3600,
                    len(result.factors_used),
                )
        except Exception as e:
            logger.error("Shadow calculation error: %s", e, exc_info=True)

        elapsed = (datetime.now(timezone.utc) - start).total_seconds()
        await asyncio.sleep(max(0, SHADOW_CALC_INTERVAL - elapsed))


async def correlation_loop(pool: asyncpg.Pool) -> None:
    """Runs once daily at 00:00 UTC."""
    global _last_corr_run

    while True:
        now = datetime.now(timezone.utc)
        # Calculate seconds until next midnight UTC
        today_midnight = now.replace(hour=0, minute=0, second=0, microsecond=0)
        tomorrow_midnight = today_midnight + timedelta(days=1)
        sleep_seconds = (tomorrow_midnight - now).total_seconds()

        logger.info("Correlation engine will run in %.1fh", sleep_seconds / 3600)
        await asyncio.sleep(sleep_seconds)

        try:
            await run_correlations(pool)
            _last_corr_run = datetime.now(timezone.utc)
        except Exception as e:
            logger.error("Correlation engine error: %s", e)


# ── Health endpoint ────────────────────────────────────────────────────────────

class HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/health":
            body = json.dumps({
                "status": "ok",
                "last_shadow_time": _last_shadow.time.isoformat() if _last_shadow else None,
                "last_shadow_price": _last_shadow.shadow_price if _last_shadow else None,
                "last_corr_run": _last_corr_run.isoformat() if _last_corr_run else None,
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
    server = HTTPServer(("0.0.0.0", 8002), HealthHandler)
    Thread(target=server.serve_forever, daemon=True).start()
    logger.info("Health endpoint: http://0.0.0.0:8002/health")


# ── Entry point ────────────────────────────────────────────────────────────────

async def main():
    logger.info("Starting calculator (interval=%ds, k=%.1f)", SHADOW_CALC_INTERVAL, CONFIDENCE_K)

    pool = await asyncpg.create_pool(DATABASE_URL, min_size=2, max_size=5)

    start_health_server()

    loop = asyncio.get_running_loop()
    stop_event = asyncio.Event()

    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, stop_event.set)

    tasks = [
        asyncio.create_task(shadow_loop(pool)),
        asyncio.create_task(correlation_loop(pool)),
    ]

    await stop_event.wait()

    for task in tasks:
        task.cancel()

    await asyncio.gather(*tasks, return_exceptions=True)
    await pool.close()
    logger.info("Calculator stopped")


if __name__ == "__main__":
    asyncio.run(main())
