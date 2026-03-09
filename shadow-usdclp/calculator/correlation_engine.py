"""
Correlation & Regression Engine

Runs daily (at 00:00 UTC) and computes:
- Pearson correlation of daily returns for each factor pair vs USDCLP
- Simple linear regression beta and R²
- Multi-factor OLS regression
- Saves results to correlation_snapshots table
"""

import json
import logging
from datetime import datetime, timezone

import asyncpg
import numpy as np
import pandas as pd
from scipy import stats
import statsmodels.api as sm

logger = logging.getLogger(__name__)

WINDOW_DAYS = [30, 60, 90, 180]

FACTOR_SYMBOLS = ["USDBRL", "USDMXN", "USDCOP", "DXY", "COPPER", "VIX", "US10Y", "ECH"]
INVERTED = {"COPPER", "ECH"}  # These move inversely with USDCLP

USDCLP_SYMBOLS = ["USDCLP", "USDCLP_SPOT", "USDCLP_OBS", "USDCLP_USDT"]


async def fetch_daily_prices(pool: asyncpg.Pool, symbol: str, days: int) -> pd.Series:
    """Fetch daily close prices (last value of each day) for a symbol."""
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT
                time_bucket('1 day', time) AS day,
                LAST(mid, time) AS close
            FROM price_ticks
            WHERE symbol = $1
              AND time > NOW() - ($2 || ' days')::INTERVAL
            GROUP BY day
            ORDER BY day
            """,
            symbol,
            str(days + 5),  # a bit extra for returns calculation
        )
    if not rows:
        return pd.Series(dtype=float)

    dates = [r["day"].date() for r in rows]
    values = [float(r["close"]) for r in rows]
    return pd.Series(values, index=pd.DatetimeIndex(dates), name=symbol)


async def fetch_shadow_daily(pool: asyncpg.Pool, days: int) -> pd.Series:
    """Fetch daily shadow prices from the shadow_usdclp table."""
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT
                time_bucket('1 day', time) AS day,
                LAST(shadow_price, time) AS close
            FROM shadow_usdclp
            WHERE time > NOW() - ($1 || ' days')::INTERVAL
            GROUP BY day
            ORDER BY day
            """,
            str(days + 5),
        )
    if not rows:
        return pd.Series(dtype=float)

    dates = [r["day"].date() for r in rows]
    values = [float(r["close"]) for r in rows]
    return pd.Series(values, index=pd.DatetimeIndex(dates), name="SHADOW")


async def get_usdclp_series(pool: asyncpg.Pool, days: int) -> pd.Series:
    """Get best available USDCLP daily series (BEC > OBS > Buda)."""
    for sym in ["USDCLP_BEC", "USDCLP_OBS", "USDCLP"]:
        series = await fetch_daily_prices(pool, sym, days)
        if len(series) >= 10:
            return series.rename("USDCLP")
    return pd.Series(dtype=float)


def daily_returns(series: pd.Series) -> pd.Series:
    return series.pct_change().dropna()


async def run_correlations(pool: asyncpg.Pool) -> None:
    now = datetime.now(timezone.utc)
    logger.info("Running correlation engine at %s", now.isoformat())

    records = []

    for window in WINDOW_DAYS:
        usdclp = await get_usdclp_series(pool, window)
        if len(usdclp) < 10:
            logger.warning("Insufficient USDCLP data for %d-day window", window)
            continue

        usdclp_ret = daily_returns(usdclp)

        for symbol in FACTOR_SYMBOLS:
            factor = await fetch_daily_prices(pool, symbol, window)
            if len(factor) < 10:
                logger.debug("Insufficient data for %s (%d-day window)", symbol, window)
                continue

            # Invert if needed
            if symbol in INVERTED:
                factor = 1 / factor

            factor_ret = daily_returns(factor)

            # Align
            combined = pd.concat([usdclp_ret, factor_ret.rename(symbol)], axis=1).dropna()
            if len(combined) < 10:
                continue

            y = combined["USDCLP"].values
            x = combined[symbol].values

            # Pearson correlation
            corr, _ = stats.pearsonr(x, y)

            # Simple linear regression
            slope, intercept, r, p, stderr = stats.linregress(x, y)
            r_sq = r ** 2

            records.append({
                "time": now,
                "window_days": window,
                "pair_a": "USDCLP",
                "pair_b": symbol,
                "correlation": float(corr),
                "r_squared": float(r_sq),
                "beta": float(slope),
                "observations": len(combined),
            })

            logger.debug(
                "%d-day USDCLP vs %s: corr=%.3f, R²=%.3f, beta=%.4f",
                window, symbol, corr, r_sq, slope
            )

        # Shadow vs real USDCLP correlation
        shadow_series = await fetch_shadow_daily(pool, window)
        if len(shadow_series) >= 10:
            shadow_ret = daily_returns(shadow_series)
            combined = pd.concat([usdclp_ret, shadow_ret.rename("SHADOW")], axis=1).dropna()
            if len(combined) >= 10:
                y = combined["USDCLP"].values
                x = combined["SHADOW"].values
                corr, _ = stats.pearsonr(x, y)
                slope, _, r, _, _ = stats.linregress(x, y)
                records.append({
                    "time": now,
                    "window_days": window,
                    "pair_a": "USDCLP",
                    "pair_b": "SHADOW_USDCLP",
                    "correlation": float(corr),
                    "r_squared": float(r ** 2),
                    "beta": float(slope),
                    "observations": len(combined),
                })

    if not records:
        logger.warning("No correlation records computed")
        return

    async with pool.acquire() as conn:
        await conn.executemany(
            """
            INSERT INTO correlation_snapshots
                (time, window_days, pair_a, pair_b, correlation, r_squared, beta, observations)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
            """,
            [(
                r["time"], r["window_days"], r["pair_a"], r["pair_b"],
                r["correlation"], r["r_squared"], r["beta"], r["observations"],
            ) for r in records],
        )

    logger.info("Saved %d correlation records", len(records))


async def run_multifactor_regression(
    pool: asyncpg.Pool, window_start: str, window_end: str
) -> dict:
    """
    Run OLS multi-factor regression of all factors vs USDCLP daily returns.
    Returns proposed betas, R², RMSE, p-values.
    """
    # Fetch all series
    days = 365  # max window; filter by date in query

    usdclp = await get_usdclp_series(pool, days)
    if len(usdclp) < 20:
        raise ValueError("Insufficient USDCLP data for regression")

    # Filter by window
    usdclp = usdclp[window_start:window_end]
    usdclp_ret = daily_returns(usdclp)

    factor_data = {}
    for symbol in FACTOR_SYMBOLS:
        series = await fetch_daily_prices(pool, symbol, days)
        if symbol in INVERTED and len(series) > 0:
            series = 1 / series
        if len(series) >= 20:
            series = series[window_start:window_end]
            factor_data[symbol] = daily_returns(series)

    if not factor_data:
        raise ValueError("No factor data available")

    # Combine and align
    combined = pd.concat([usdclp_ret.rename("USDCLP")] + [s.rename(sym) for sym, s in factor_data.items()], axis=1).dropna()

    if len(combined) < 20:
        raise ValueError(f"Only {len(combined)} aligned observations, need ≥20")

    y = combined["USDCLP"].values
    X_cols = [c for c in combined.columns if c != "USDCLP"]
    X = sm.add_constant(combined[X_cols].values)

    model = sm.OLS(y, X).fit()

    # Map coefficients back to beta keys
    beta_map = {
        "USDBRL": "beta_usdbrl",
        "USDMXN": "beta_usdmxn",
        "USDCOP": "beta_usdcop",
        "DXY": "beta_dxy",
        "COPPER": "beta_copper_inv",
        "VIX": "beta_vix",
        "US10Y": "beta_us10y",
        "ECH": "beta_ech",
    }

    proposed_params = {}
    pvalues = {}
    for i, col in enumerate(X_cols):
        beta_key = beta_map.get(col, col.lower())
        proposed_params[beta_key] = round(float(model.params[i + 1]), 4)
        pvalues[beta_key] = round(float(model.pvalues[i + 1]), 4)

    residuals = model.resid
    rmse = float(np.sqrt(np.mean(residuals ** 2)))

    return {
        "proposed_params": proposed_params,
        "r_squared": round(float(model.rsquared), 4),
        "rmse": round(rmse, 6),
        "pvalues": pvalues,
        "observations": len(combined),
        "window_start": window_start,
        "window_end": window_end,
    }
