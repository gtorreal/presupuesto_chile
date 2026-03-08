"""
Public API endpoints — authenticated via API key (X-API-Key header).

These endpoints are excluded from JWT middleware and validated here directly.
"""

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, Request

from auth import hash_api_key
from routes.shadow import parse_jsonb

router = APIRouter(prefix="/api/v1/public", tags=["Public API"])


async def validate_api_key(request: Request) -> dict:
    """Dependency: validate X-API-Key header and return user info."""
    api_key = request.headers.get("X-API-Key")
    if not api_key:
        raise HTTPException(status_code=401, detail="Missing X-API-Key header")

    key_hash = hash_api_key(api_key)
    pool = request.app.state.pool

    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT ak.id AS key_id, ak.user_id, u.username
            FROM api_keys ak
            JOIN users u ON u.id = ak.user_id
            WHERE ak.key_hash = $1 AND ak.is_active = TRUE AND u.is_active = TRUE
            """,
            key_hash,
        )
        if not row:
            raise HTTPException(status_code=401, detail="Invalid or revoked API key")

        # Debounce: only update last_used_at if older than 1 minute
        await conn.execute(
            """
            UPDATE api_keys SET last_used_at = NOW()
            WHERE id = $1 AND (last_used_at IS NULL OR last_used_at < NOW() - INTERVAL '1 minute')
            """,
            row["key_id"],
        )

    return {"username": row["username"], "user_id": row["user_id"]}


@router.get("/prices/current", summary="Precio shadow actual")
async def public_current_price(
    request: Request,
    _user: dict = Depends(validate_api_key),
):
    """
    Retorna el precio shadow USDCLP más reciente con banda de confianza.

    **Autenticación**: Header `X-API-Key: sk_shadow_...`
    """
    pool = request.app.state.pool

    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT time, shadow_price, confidence_low, confidence_high,
                   bec_last_close, bec_close_time, factors_used, factor_deltas, model_version
            FROM shadow_usdclp
            ORDER BY time DESC LIMIT 1
            """
        )

    if not row:
        raise HTTPException(status_code=503, detail="No shadow price available yet")

    now = datetime.now(timezone.utc)
    bec_age_hours = (
        (now - row["bec_close_time"]).total_seconds() / 3600
        if row["bec_close_time"]
        else None
    )

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


@router.get("/prices/history", summary="Historial de precios shadow")
async def public_price_history(
    request: Request,
    hours: int = Query(default=24, ge=1, le=168, description="Horas de historial (máx 168 = 7 días)"),
    _user: dict = Depends(validate_api_key),
):
    """
    Retorna el historial de precios shadow USDCLP.

    **Autenticación**: Header `X-API-Key: sk_shadow_...`

    Máximo 7 días (168 horas) de historial por request.
    """
    pool = request.app.state.pool

    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT time, shadow_price, confidence_low, confidence_high,
                   bec_last_close, model_version
            FROM shadow_usdclp
            WHERE time > NOW() - ($1 || ' hours')::INTERVAL
            ORDER BY time ASC
            """,
            str(hours),
        )

    return {
        "count": len(rows),
        "hours": hours,
        "data": [
            {
                "time": r["time"].isoformat(),
                "shadow_price": r["shadow_price"],
                "confidence_low": r["confidence_low"],
                "confidence_high": r["confidence_high"],
                "bec_last_close": r["bec_last_close"],
                "model_version": r["model_version"],
            }
            for r in rows
        ],
    }
