"""
Endpoint para tabla de precios históricos.
Consulta directamente price_ticks (time-bucketed) + shadow_usdclp.
"""

from fastapi import APIRouter, Query, Request

router = APIRouter()

# Símbolos que pivotamos en columnas.  (db_symbol, json_key)
SYMBOLS = [
    ("USDCLP",      "usdclp_buda"),
    ("USDCLP_USDT", "usdclp_usdt"),
    ("USDCLP_SPOT", "usdclp_spot"),
    ("USDCLP_NDF",  "usdclp_ndf"),
    ("USDBRL",      "usdbrl"),
    ("USDMXN",      "usdmxn"),
    ("USDCOP",      "usdcop"),
    ("DXY",         "dxy"),
    ("DXY_PROXY",   "dxy_proxy"),
    ("COPPER",      "copper"),
    ("VIX",         "vix"),
    ("US10Y",       "us10y"),
    ("ECH",         "ech"),
]

# Bucket size adapts to time range to keep row counts manageable.
def _bucket_interval(hours: int) -> str:
    if hours <= 6:
        return "1 minute"
    if hours <= 24:
        return "5 minutes"
    if hours <= 48:
        return "10 minutes"
    if hours <= 168:
        return "30 minutes"
    return "1 hour"


def _build_pivot_sql() -> str:
    """Build the CASE columns for symbol pivot."""
    parts = []
    for db_sym, key in SYMBOLS:
        parts.append(
            f"MAX(CASE WHEN symbol = '{db_sym}' THEN mid END) AS {key}"
        )
    return ",\n            ".join(parts)


@router.get("/price-ticks/table")
async def get_price_ticks_table(
    request: Request,
    hours: int = Query(default=24, ge=1, le=8760),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=10, le=200),
):
    """
    Tabla paginada de precios reales por time bucket.
    Pivotea todos los símbolos en columnas e incluye shadow USDCLP.
    Consulta directamente price_ticks (fuente de verdad).
    """
    pool = request.app.state.pool
    bucket = _bucket_interval(hours)
    pivot_cols = _build_pivot_sql()
    offset = (page - 1) * page_size

    # bucket is a hardcoded value from _bucket_interval, safe to interpolate
    async with pool.acquire() as conn:
        # Count total buckets for pagination
        total = await conn.fetchval(
            f"""
            SELECT COUNT(DISTINCT time_bucket('{bucket}'::INTERVAL, time))
            FROM price_ticks
            WHERE time > NOW() - ($1 || ' hours')::INTERVAL
              AND time <= NOW()
            """,
            str(hours),
        )

        # Pivoted prices + shadow price per bucket
        rows = await conn.fetch(
            f"""
            WITH buckets AS (
                SELECT
                    time_bucket('{bucket}'::INTERVAL, time) AS bucket,
                    {pivot_cols}
                FROM price_ticks
                WHERE time > NOW() - ($1 || ' hours')::INTERVAL
                  AND time <= NOW()
                GROUP BY bucket
            ),
            shadow AS (
                SELECT
                    time_bucket('{bucket}'::INTERVAL, time) AS bucket,
                    (array_agg(shadow_price ORDER BY time DESC))[1] AS shadow_price
                FROM shadow_usdclp
                WHERE time > NOW() - ($1 || ' hours')::INTERVAL
                  AND time <= NOW()
                GROUP BY bucket
            )
            SELECT
                b.bucket AS time,
                {', '.join(f'b.{key}' for _, key in SYMBOLS)},
                s.shadow_price
            FROM buckets b
            LEFT JOIN shadow s ON b.bucket = s.bucket
            ORDER BY b.bucket DESC
            LIMIT $2 OFFSET $3
            """,
            str(hours),
            page_size,
            offset,
        )

    total_pages = max(1, -(-total // page_size))  # ceil division

    return {
        "page": page,
        "page_size": page_size,
        "total_rows": total,
        "total_pages": total_pages,
        "bucket_interval": bucket,
        "symbols": [key for _, key in SYMBOLS],
        "rows": [
            {
                "time": r["time"].isoformat(),
                **{key: r[key] for _, key in SYMBOLS},
                "shadow_price": r["shadow_price"],
            }
            for r in rows
        ],
    }
