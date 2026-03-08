import json
import sys
import os

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel


def _json(v):
    if v is None:
        return {}
    if isinstance(v, str):
        return json.loads(v)
    return dict(v)

router = APIRouter()


@router.get("/model/params")
async def get_model_params(request: Request):
    """Active and historical model parameters."""
    pool = request.app.state.pool

    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT id, created_at, name, is_active, params, training_window,
                   r_squared, rmse, notes
            FROM model_params
            ORDER BY created_at DESC
            """
        )

    result = {
        "active": None,
        "history": [],
    }
    for r in rows:
        entry = {
            "id": r["id"],
            "name": r["name"],
            "is_active": r["is_active"],
            "params": _json(r["params"]),
            "training_window": r["training_window"],
            "r_squared": r["r_squared"],
            "rmse": r["rmse"],
            "notes": r["notes"],
            "created_at": r["created_at"].isoformat(),
        }
        if r["is_active"]:
            result["active"] = entry
        result["history"].append(entry)

    return result


class RecalibrateRequest(BaseModel):
    window_start: str  # "YYYY-MM-DD"
    window_end: str


@router.post("/model/recalibrate")
async def recalibrate_model(req: RecalibrateRequest, request: Request):
    """
    Run OLS multi-factor regression and propose new betas.
    Does NOT activate them — use /model/activate to do that.
    """
    pool = request.app.state.pool

    # Import here to avoid loading heavy deps at startup
    sys.path.insert(0, "/app")
    try:
        from correlation_engine import run_multifactor_regression
    except ImportError:
        raise HTTPException(status_code=501, detail="Regression engine not available in API service")

    try:
        result = await run_multifactor_regression(pool, req.window_start, req.window_end)
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


class ActivateRequest(BaseModel):
    param_id: int
    name: str | None = None


@router.post("/model/activate")
async def activate_model(req: ActivateRequest, request: Request):
    """Activate a specific model param set (deactivates all others)."""
    pool = request.app.state.pool

    async with pool.acquire() as conn:
        # Check it exists
        exists = await conn.fetchval(
            "SELECT COUNT(*) FROM model_params WHERE id = $1", req.param_id
        )
        if not exists:
            raise HTTPException(status_code=404, detail="Model params not found")

        # Deactivate all, then activate the selected one
        async with conn.transaction():
            await conn.execute("UPDATE model_params SET is_active = FALSE")
            await conn.execute(
                "UPDATE model_params SET is_active = TRUE WHERE id = $1", req.param_id
            )

    return {"success": True, "activated_id": req.param_id}


class SaveParamsRequest(BaseModel):
    name: str
    params: dict
    notes: str | None = None


@router.post("/model/params")
async def save_params(req: SaveParamsRequest, request: Request):
    """Save a new set of model params (without activating)."""
    import json

    pool = request.app.state.pool

    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            INSERT INTO model_params (name, is_active, params, notes)
            VALUES ($1, FALSE, $2::jsonb, $3)
            RETURNING id, created_at
            """,
            req.name,
            json.dumps(req.params),
            req.notes,
        )

    return {"id": row["id"], "created_at": row["created_at"].isoformat()}
