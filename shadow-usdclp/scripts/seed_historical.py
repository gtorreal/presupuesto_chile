#!/usr/bin/env python3
"""
Seed historical data for Shadow USDCLP.

Downloads ~6 months of historical data from free sources:
- mindicador.cl: USDCLP observed (daily, free)
- Buda.com: USDC-CLP trades (public, no auth)

Run with:
    python scripts/seed_historical.py

Requires DATABASE_URL env var.
"""

import asyncio
import json
import logging
import os
from datetime import datetime, timezone

import aiohttp
import asyncpg

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
logger = logging.getLogger("seed")

DATABASE_URL = os.environ["DATABASE_URL"]

# Fetch last 6 months of dólar observado from mindicador
MINDICADOR_URL = "https://mindicador.cl/api/dolar"

# Buda.com public trade history
BUDA_TRADES_URL = "https://www.buda.com/api/v2/markets/{market}/trades"


async def seed_mindicador(pool: asyncpg.Pool, session: aiohttp.ClientSession):
    logger.info("Fetching mindicador historical data...")
    async with session.get(MINDICADOR_URL, timeout=aiohttp.ClientTimeout(total=30)) as resp:
        resp.raise_for_status()
        data = await resp.json(content_type=None)

    series = data.get("serie", [])
    logger.info("Got %d mindicador records", len(series))

    rows = []
    for item in series:
        try:
            value = float(item["valor"])
            fecha_str = item["fecha"]
            tick_time = datetime.fromisoformat(fecha_str.replace("Z", "+00:00"))
            rows.append((
                tick_time, "mindicador", "USDCLP_OBS",
                None, None, value, None,
                json.dumps({"valor": value, "fecha": fecha_str}),
            ))
        except Exception as e:
            logger.warning("Skipping mindicador record: %s", e)

    if rows:
        async with pool.acquire() as conn:
            await conn.executemany(
                """
                INSERT INTO price_ticks (time, source, symbol, bid, ask, mid, volume, raw_json)
                VALUES ($1,$2,$3,$4,$5,$6,$7,$8::jsonb)
                ON CONFLICT DO NOTHING
                """,
                rows,
            )
        logger.info("Inserted %d mindicador records", len(rows))


async def seed_buda(pool: asyncpg.Pool, session: aiohttp.ClientSession):
    markets = [
        ("usdc-clp", "USDCLP"),
        ("usdt-clp", "USDCLP_USDT"),
    ]

    for market, symbol in markets:
        logger.info("Fetching Buda %s historical trades...", market)
        url = BUDA_TRADES_URL.format(market=market)

        rows = []
        last_timestamp = None

        # Buda returns up to 100 trades per page, paginate backwards
        for page in range(50):  # max 5000 trades
            params = {}
            if last_timestamp:
                params["timestamp"] = last_timestamp

            try:
                async with session.get(url, params=params, timeout=aiohttp.ClientTimeout(total=15)) as resp:
                    resp.raise_for_status()
                    data = await resp.json()
            except Exception as e:
                logger.error("Buda trades error: %s", e)
                break

            trades = data.get("trades", {}).get("entries", [])
            if not trades:
                break

            for trade in trades:
                # Trade format: [timestamp_ms, price, amount, direction]
                try:
                    ts_ms = int(trade[0])
                    price = float(trade[1])
                    amount = float(trade[2])
                    tick_time = datetime.fromtimestamp(ts_ms / 1000, tz=timezone.utc)
                    rows.append((
                        tick_time, "buda", symbol,
                        None, None, price, amount,
                        json.dumps({"ts": ts_ms, "price": price, "amount": amount}),
                    ))
                    last_timestamp = ts_ms
                except Exception:
                    continue

            logger.info("Page %d: %d trades (total so far: %d)", page + 1, len(trades), len(rows))
            await asyncio.sleep(0.5)  # be polite

        if rows:
            async with pool.acquire() as conn:
                await conn.executemany(
                    """
                    INSERT INTO price_ticks (time, source, symbol, bid, ask, mid, volume, raw_json)
                    VALUES ($1,$2,$3,$4,$5,$6,$7,$8::jsonb)
                    ON CONFLICT DO NOTHING
                    """,
                    rows,
                )
            logger.info("Inserted %d Buda %s records", len(rows), market)


async def main():
    logger.info("Connecting to database...")
    pool = await asyncpg.create_pool(DATABASE_URL, min_size=1, max_size=3)

    async with aiohttp.ClientSession() as session:
        await seed_mindicador(pool, session)
        await seed_buda(pool, session)

    await pool.close()
    logger.info("Seed complete!")


if __name__ == "__main__":
    asyncio.run(main())
