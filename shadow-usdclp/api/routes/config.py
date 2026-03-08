from fastapi import APIRouter, Request
from pydantic import BaseModel

router = APIRouter()

CONFIG_KEYS = {
    "collector_fast_interval",
    "collector_yfinance_interval",
    "calculator_interval",
}


@router.get("/config")
async def get_config(request: Request):
    pool = request.app.state.pool
    async with pool.acquire() as conn:
        rows = await conn.fetch("SELECT key, value, updated_at FROM system_config")
    return {r["key"]: {"value": int(r["value"]), "updated_at": r["updated_at"].isoformat()} for r in rows}


class ConfigPatch(BaseModel):
    key: str
    value: int


@router.patch("/config")
async def patch_config(req: ConfigPatch, request: Request):
    if req.key not in CONFIG_KEYS:
        from fastapi import HTTPException
        raise HTTPException(status_code=400, detail=f"Unknown config key: {req.key}")
    if req.value < 5:
        from fastapi import HTTPException
        raise HTTPException(status_code=400, detail="Minimum interval is 5 seconds")

    pool = request.app.state.pool
    async with pool.acquire() as conn:
        await conn.execute(
            "UPDATE system_config SET value = $1, updated_at = NOW() WHERE key = $2",
            str(req.value), req.key,
        )
    return {"ok": True, "key": req.key, "value": req.value}
