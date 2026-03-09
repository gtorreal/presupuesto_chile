import json
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Query, Request


def parse_jsonb(v):
    """Safely convert asyncpg JSONB value (may be str or dict) to dict."""
    if v is None:
        return {}
    if isinstance(v, str):
        return json.loads(v)
    return dict(v)

router = APIRouter()


@router.get("/shadow-price")
async def get_shadow_price(request: Request):
    """Latest shadow USDCLP price with confidence band and factor breakdown."""
    pool = request.app.state.pool

    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT
                time, shadow_price, confidence_low, confidence_high,
                bec_last_close, bec_close_time, factors_used, factor_deltas, model_version
            FROM shadow_usdclp
            ORDER BY time DESC LIMIT 1
            """
        )

    if not row:
        raise HTTPException(status_code=503, detail="No shadow price available yet")

    now = datetime.now(timezone.utc)
    bec_age_hours = (now - row["bec_close_time"]).total_seconds() / 3600 if row["bec_close_time"] else None

    return {
        "shadow_usdclp": row["shadow_price"],
        "confidence_low": row["confidence_low"],
        "confidence_high": row["confidence_high"],
        "bec_last_close": row["bec_last_close"],
        "bec_close_age_hours": round(bec_age_hours, 2) if bec_age_hours is not None else None,
        "bec_close_time": row["bec_close_time"].isoformat() if row["bec_close_time"] else None,
        "factors": parse_jsonb(row["factors_used"]),
        "factor_deltas": parse_jsonb(row["factor_deltas"]),
        "model_version": row["model_version"],
        "timestamp": row["time"].isoformat(),
    }


@router.get("/shadow-price/history")
async def get_shadow_history(request: Request, hours: int = Query(default=24, ge=1, le=720)):
    """Historical shadow prices for charting."""
    pool = request.app.state.pool

    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT
                s.time, s.shadow_price, s.confidence_low, s.confidence_high,
                s.factor_deltas, s.model_version,
                pt_spot.mid  AS usdclp_spot,
                pt_usdc.mid  AS usdclp_buda,
                pt_usdt.mid  AS usdclp_usdt
            FROM shadow_usdclp s
            LEFT JOIN LATERAL (
                SELECT mid FROM price_ticks
                WHERE symbol = 'USDCLP_SPOT' AND time <= s.time
                ORDER BY time DESC LIMIT 1
            ) pt_spot ON true
            LEFT JOIN LATERAL (
                SELECT mid FROM price_ticks
                WHERE symbol = 'USDCLP' AND time <= s.time
                ORDER BY time DESC LIMIT 1
            ) pt_usdc ON true
            LEFT JOIN LATERAL (
                SELECT mid FROM price_ticks
                WHERE symbol = 'USDCLP_USDT' AND time <= s.time
                ORDER BY time DESC LIMIT 1
            ) pt_usdt ON true
            WHERE s.time > NOW() - ($1 || ' hours')::INTERVAL
            ORDER BY s.time ASC
            """,
            str(hours),
        )

    return [
        {
            "time": r["time"].isoformat(),
            "shadow_price": r["shadow_price"],
            "confidence_low": r["confidence_low"],
            "confidence_high": r["confidence_high"],
            "factor_deltas": parse_jsonb(r["factor_deltas"]),
            "model_version": r["model_version"],
            "usdclp_spot": float(r["usdclp_spot"]) if r["usdclp_spot"] is not None else None,
            "usdclp_buda": float(r["usdclp_buda"]) if r["usdclp_buda"] is not None else None,
            "usdclp_usdt": float(r["usdclp_usdt"]) if r["usdclp_usdt"] is not None else None,
        }
        for r in rows
    ]


@router.get("/sources/status")
async def get_sources_status(request: Request):
    """Check which data sources are actively delivering data."""
    pool = request.app.state.pool

    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT
                source,
                COUNT(*) AS tick_count,
                MAX(time) AS last_tick,
                EXTRACT(EPOCH FROM (NOW() - MAX(time))) / 60 AS minutes_ago
            FROM price_ticks
            WHERE time > NOW() - INTERVAL '2 hours'
            GROUP BY source
            ORDER BY source
            """
        )

    return [
        {
            "source": r["source"],
            "tick_count_2h": r["tick_count"],
            "last_tick": r["last_tick"].isoformat(),
            "minutes_ago": round(float(r["minutes_ago"]), 1),
            "is_live": float(r["minutes_ago"]) < 5,
        }
        for r in rows
    ]
