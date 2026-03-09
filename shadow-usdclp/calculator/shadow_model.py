"""
Shadow USDCLP Model

Formula:
    Shadow_USDCLP(t) = BEC_Last_Close × (1 + Σ βᵢ × Δ%Factorᵢ(t))

Where:
    Δ%Factor(t) = (Factor_now - Factor_at_BEC_close) / Factor_at_BEC_close
    βᵢ come from model_params table (is_active = TRUE)
    Copper is inverted (copper↑ → CLP↑ → USDCLP↓)

Confidence band:
    spread_half = k × σ_model × √(hours_since_bec_close / 24)
"""

import json
import logging
import math
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

import asyncpg

logger = logging.getLogger(__name__)

# Symbol mapping: beta_key → DB symbol name
BETA_TO_SYMBOL: dict[str, str] = {
    "beta_ndf": "USDCLP_NDF",
    "beta_usdbrl": "USDBRL",
    "beta_dxy": "DXY",
    "beta_copper_inv": "COPPER",
    "beta_usdmxn": "USDMXN",
    "beta_vix": "VIX",
    "beta_us10y": "US10Y",
    "beta_usdcop": "USDCOP",
    "beta_ech": "ECH",
}

# Inverted factors (higher price → lower USDCLP)
INVERTED_FACTORS = {"beta_copper_inv", "beta_ech"}

# Proxy fallbacks: if primary symbol has no recent data, try these alternatives.
# DXY_PROXY comes from Frankfurter (EUR/USD inverted); VIX_PROXY from VIXY ETF.
SYMBOL_FALLBACKS: dict[str, list[str]] = {
    "DXY": ["DXY_PROXY"],
    "VIX": ["VIX_PROXY"],
}


@dataclass
class ShadowResult:
    time: datetime
    shadow_price: float
    confidence_low: float
    confidence_high: float
    bec_last_close: float
    bec_close_time: datetime
    factors_used: dict
    factor_deltas: dict
    model_version: str


async def get_active_params(pool: asyncpg.Pool) -> tuple[dict, str]:
    """Returns (params_dict, model_name) for the active model."""
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT name, params FROM model_params WHERE is_active = TRUE ORDER BY created_at DESC LIMIT 1"
        )
    if not row:
        raise RuntimeError("No active model params found in DB")
    params = row["params"]
    if isinstance(params, str):
        params = json.loads(params)
    return dict(params), row["name"]


async def get_latest_price(pool: asyncpg.Pool, symbol: str) -> Optional[float]:
    """Get the most recent mid price for a symbol (last 10 minutes).
    Falls back to proxy symbols (e.g. DXY → DXY_PROXY) if primary is unavailable."""
    symbols_to_try = [symbol] + SYMBOL_FALLBACKS.get(symbol, [])
    async with pool.acquire() as conn:
        for sym in symbols_to_try:
            row = await conn.fetchrow(
                """
                SELECT mid FROM price_ticks
                WHERE symbol = $1
                  AND time > NOW() - INTERVAL '10 minutes'
                ORDER BY time DESC LIMIT 1
                """,
                sym,
            )
            if row:
                if sym != symbol:
                    logger.debug("Using fallback %s for %s (latest)", sym, symbol)
                return float(row["mid"])
    return None


async def get_price_at_bec_close(pool: asyncpg.Pool, symbol: str, bec_close_time: datetime) -> Optional[float]:
    """
    Get the price of a symbol at the BEC close time.
    Falls back to proxy symbols (e.g. DXY → DXY_PROXY) if primary is unavailable.

    Search strategy (in order, for each symbol variant):
    1. Closest tick within ±2h of BEC close time (ideal).
    2. Oldest available tick within 6h of BEC close (initial setup fallback).
    3. Last available tick before now (weekend/holiday fallback — markets closed,
       so the last known price IS the correct reference price).
    """
    symbols_to_try = [symbol] + SYMBOL_FALLBACKS.get(symbol, [])
    async with pool.acquire() as conn:
        for sym in symbols_to_try:
            # Primary: look near the BEC close
            row = await conn.fetchrow(
                """
                SELECT mid FROM price_ticks
                WHERE symbol = $1
                  AND time BETWEEN $2::timestamptz - INTERVAL '2 hours' AND $2::timestamptz + INTERVAL '2 hours'
                ORDER BY ABS(EXTRACT(EPOCH FROM (time - $2::timestamptz))) LIMIT 1
                """,
                sym,
                bec_close_time,
            )
            if row:
                if sym != symbol:
                    logger.debug("Using fallback %s for %s (at_close)", sym, symbol)
                return float(row["mid"])

            # Fallback 1: oldest tick within 6h of BEC close (initial setup).
            row = await conn.fetchrow(
                "SELECT mid, time FROM price_ticks WHERE symbol = $1 ORDER BY time ASC LIMIT 1",
                sym,
            )
            if row:
                age_hours = abs((row["time"] - bec_close_time).total_seconds()) / 3600
                if age_hours <= 6:
                    if sym != symbol:
                        logger.debug("Using fallback %s for %s (at_close, oldest)", sym, symbol)
                    return float(row["mid"])

        # Fallback 2: last available tick for any symbol variant.
        # Handles weekends/holidays where BEC close timestamp may be in the future
        # and no ticks exist near that time. The last known price is the best reference.
        for sym in symbols_to_try:
            row = await conn.fetchrow(
                "SELECT mid FROM price_ticks WHERE symbol = $1 ORDER BY time DESC LIMIT 1",
                sym,
            )
            if row:
                logger.debug("Using last available price for %s (at_close, last-known)", sym)
                return float(row["mid"])
    return None


async def get_bec_last_close(pool: asyncpg.Pool) -> tuple[float, datetime]:
    """
    Get the most recent official BEC close price and its time.
    Priority: bec_stub > USDCLP_OBS (mindicador/CMF)
    Falls back to last Buda USDCLP tick if nothing else available.
    """
    async with pool.acquire() as conn:
        # Try BEC stub first
        row = await conn.fetchrow(
            """
            SELECT mid, time FROM price_ticks
            WHERE symbol = 'USDCLP_BEC'
            ORDER BY time DESC LIMIT 1
            """
        )
        if row:
            return float(row["mid"]), row["time"]

        # Try observed dollar (mindicador/CMF)
        row = await conn.fetchrow(
            """
            SELECT mid, time FROM price_ticks
            WHERE symbol = 'USDCLP_OBS'
            ORDER BY time DESC LIMIT 1
            """
        )
        if row:
            return float(row["mid"]), row["time"]

        # Fall back to Buda USDC-CLP
        row = await conn.fetchrow(
            """
            SELECT mid, time FROM price_ticks
            WHERE symbol = 'USDCLP' AND source = 'buda'
            ORDER BY time DESC LIMIT 1
            """
        )
        if row:
            return float(row["mid"]), row["time"]

    raise RuntimeError("No BEC close data available")


async def get_model_error_stddev(pool: asyncpg.Pool) -> float:
    """
    Estimate σ_model from the last 60 shadow price errors during BEC overlap hours.
    Falls back to a default 3.0 if insufficient data.
    """
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT s.shadow_price, p.mid AS real_price
            FROM shadow_usdclp s
            JOIN LATERAL (
                SELECT mid FROM price_ticks
                WHERE symbol IN ('USDCLP', 'USDCLP_OBS')
                  AND time BETWEEN s.time - INTERVAL '5 minutes' AND s.time + INTERVAL '5 minutes'
                ORDER BY ABS(EXTRACT(EPOCH FROM (time - s.time))) LIMIT 1
            ) p ON TRUE
            ORDER BY s.time DESC
            LIMIT 60
            """
        )

    MIN_SIGMA = 3.0  # floor: at least ±3 CLP uncertainty regardless of model accuracy

    if len(rows) < 5:
        return MIN_SIGMA

    errors = [float(r["shadow_price"]) - float(r["real_price"]) for r in rows]
    mean = sum(errors) / len(errors)
    variance = sum((e - mean) ** 2 for e in errors) / (len(errors) - 1)
    return max(math.sqrt(variance), MIN_SIGMA)


async def calculate_shadow(pool: asyncpg.Pool, confidence_k: float = 2.0, sigma: Optional[float] = None) -> Optional[ShadowResult]:
    now = datetime.now(timezone.utc)

    try:
        betas, model_name = await get_active_params(pool)
    except Exception as e:
        logger.error("Cannot load model params: %s", e)
        return None

    try:
        bec_close, bec_close_time = await get_bec_last_close(pool)
    except Exception as e:
        logger.error("Cannot get BEC close: %s", e)
        return None

    hours_since_close = (now - bec_close_time).total_seconds() / 3600

    factors_used = {}
    factor_deltas = {}
    weighted_sum = 0.0
    available_beta_sum = 0.0
    total_beta_sum = sum(abs(v) for v in betas.values())

    for beta_key, symbol in BETA_TO_SYMBOL.items():
        beta = betas.get(beta_key, 0.0)
        if beta == 0:
            continue

        price_now = await get_latest_price(pool, symbol)
        price_at_close = await get_price_at_bec_close(pool, symbol, bec_close_time)

        if price_now is None or price_at_close is None or price_at_close == 0:
            logger.debug("Factor %s unavailable (now=%s, at_close=%s)", beta_key, price_now, price_at_close)
            continue

        delta_pct = (price_now - price_at_close) / price_at_close

        # Invert factors where higher value = stronger CLP = lower USDCLP
        if beta_key in INVERTED_FACTORS:
            delta_pct = -delta_pct

        factors_used[beta_key] = {"symbol": symbol, "now": price_now, "at_close": price_at_close}
        factor_deltas[beta_key] = delta_pct
        weighted_sum += beta * delta_pct
        available_beta_sum += abs(beta)

    if not factors_used:
        # Fallback: no external factors available (no API keys configured).
        # Return BEC close as shadow price with maximally wide confidence band.
        logger.warning(
            "No factors available — returning BEC close (%.2f) as shadow price (no-adjustment fallback)",
            bec_close,
        )
        if sigma is None:
            sigma = await get_model_error_stddev(pool)
        spread_half = confidence_k * sigma * math.sqrt(max(hours_since_close, 0.01) / 24)
        return ShadowResult(
            time=now,
            shadow_price=round(bec_close, 4),
            confidence_low=round(bec_close - spread_half, 4),
            confidence_high=round(bec_close + spread_half, 4),
            bec_last_close=bec_close,
            bec_close_time=bec_close_time,
            factors_used={},
            factor_deltas={},
            model_version=f"{model_name}:no-factors",
        )

    # Renormalize if some factors are missing (cap at 3x to prevent dangerous amplification)
    MAX_RENORM_SCALE = 3.0
    if available_beta_sum < total_beta_sum and available_beta_sum > 0:
        scale = min(total_beta_sum / available_beta_sum, MAX_RENORM_SCALE)
        weighted_sum *= scale
        if total_beta_sum / available_beta_sum > MAX_RENORM_SCALE:
            logger.warning(
                "Renormalization capped at %.1fx (raw would be %.1fx) — too few factors (%d/%d)",
                MAX_RENORM_SCALE,
                total_beta_sum / available_beta_sum,
                len(factors_used),
                len(BETA_TO_SYMBOL),
            )
        else:
            logger.info(
                "Renormalizing: using %.0f%% of beta weight (%d/%d factors)",
                100 * available_beta_sum / total_beta_sum,
                len(factors_used),
                len(BETA_TO_SYMBOL),
            )

    shadow_price = bec_close * (1 + weighted_sum)

    # Confidence band
    if sigma is None:
        sigma = await get_model_error_stddev(pool)
    spread_half = confidence_k * sigma * math.sqrt(max(hours_since_close, 0.01) / 24)

    return ShadowResult(
        time=now,
        shadow_price=round(shadow_price, 4),
        confidence_low=round(shadow_price - spread_half, 4),
        confidence_high=round(shadow_price + spread_half, 4),
        bec_last_close=bec_close,
        bec_close_time=bec_close_time,
        factors_used=factors_used,
        factor_deltas=factor_deltas,
        model_version=model_name,
    )
