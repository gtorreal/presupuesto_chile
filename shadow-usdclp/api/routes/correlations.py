from fastapi import APIRouter, Request

router = APIRouter()


@router.get("/correlations")
async def get_correlations(request: Request, window: int = 90):
    """Correlation snapshot for all pairs at the given window."""
    pool = request.app.state.pool

    async with pool.acquire() as conn:
        # Get the latest snapshot for this window size
        rows = await conn.fetch(
            """
            SELECT DISTINCT ON (pair_a, pair_b)
                pair_a, pair_b, correlation, r_squared, beta, observations, time
            FROM correlation_snapshots
            WHERE window_days = $1
            ORDER BY pair_a, pair_b, time DESC
            """,
            window,
        )

    return {
        "window_days": window,
        "pairs": [
            {
                "pair_a": r["pair_a"],
                "pair_b": r["pair_b"],
                "correlation": r["correlation"],
                "r_squared": r["r_squared"],
                "beta": r["beta"],
                "observations": r["observations"],
                "as_of": r["time"].isoformat(),
            }
            for r in rows
        ],
    }


@router.get("/correlations/history")
async def get_correlation_history(request: Request, pair_b: str, window: int = 90, days: int = 180):
    """How a specific correlation evolved over time."""
    pool = request.app.state.pool

    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT time, correlation, r_squared, beta
            FROM correlation_snapshots
            WHERE pair_a = 'USDCLP'
              AND pair_b = $1
              AND window_days = $2
              AND time > NOW() - ($3 || ' days')::INTERVAL
            ORDER BY time ASC
            """,
            pair_b,
            window,
            str(days),
        )

    return [
        {
            "time": r["time"].isoformat(),
            "correlation": r["correlation"],
            "r_squared": r["r_squared"],
            "beta": r["beta"],
        }
        for r in rows
    ]
