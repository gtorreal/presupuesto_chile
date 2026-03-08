"""
API Key management routes.

Users can create, list, and revoke API keys for public API access.
Keys are shown once at creation time and stored hashed (SHA-256).
"""

import secrets

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from auth import current_user, hash_api_key
from audit import log_event

router = APIRouter(prefix="/api/v1/api-keys", tags=["API Keys"])


def _generate_key() -> str:
    """Generate a prefixed API key: sk_shadow_<40 hex chars>."""
    return f"sk_shadow_{secrets.token_hex(20)}"


class CreateKeyRequest(BaseModel):
    label: str = "default"


@router.get("")
async def list_keys(request: Request):
    """List all API keys for the current user (active and revoked)."""
    user = current_user(request)
    pool = request.app.state.pool

    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT ak.id, ak.key_prefix, ak.label, ak.created_at, ak.last_used_at, ak.is_active
            FROM api_keys ak
            JOIN users u ON u.id = ak.user_id
            WHERE u.username = $1
            ORDER BY ak.created_at DESC
            """,
            user["username"],
        )

    return [
        {
            "id": r["id"],
            "key_prefix": r["key_prefix"],
            "label": r["label"],
            "created_at": r["created_at"].isoformat(),
            "last_used_at": r["last_used_at"].isoformat() if r["last_used_at"] else None,
            "is_active": r["is_active"],
        }
        for r in rows
    ]


@router.post("")
async def create_key(body: CreateKeyRequest, request: Request):
    """Create a new API key. Returns the full key ONCE — it cannot be retrieved later."""
    user = current_user(request)
    pool = request.app.state.pool

    async with pool.acquire() as conn:
        user_id = await conn.fetchval(
            "SELECT id FROM users WHERE username = $1", user["username"]
        )
        if not user_id:
            raise HTTPException(status_code=404, detail="Usuario no encontrado")

        # Limit to 5 active keys per user
        active_count = await conn.fetchval(
            "SELECT COUNT(*) FROM api_keys WHERE user_id = $1 AND is_active = TRUE",
            user_id,
        )
        if active_count >= 5:
            raise HTTPException(
                status_code=400,
                detail="Máximo 5 keys activas por usuario. Revoca una antes de crear otra.",
            )

        raw_key = _generate_key()
        key_hash = hash_api_key(raw_key)
        key_prefix = raw_key[:16] + "..."

        await conn.execute(
            """
            INSERT INTO api_keys (user_id, key_prefix, key_hash, label)
            VALUES ($1, $2, $3, $4)
            """,
            user_id,
            key_prefix,
            key_hash,
            body.label,
        )

    client_ip = request.client.host if request.client else None
    await log_event(
        pool,
        "api_key_create",
        username=user["username"],
        ip=client_ip,
        detail={"label": body.label, "prefix": key_prefix},
    )

    return {
        "key": raw_key,
        "key_prefix": key_prefix,
        "label": body.label,
        "message": "Guarda esta key — no se puede volver a ver.",
    }


@router.delete("/{key_id}")
async def revoke_key(key_id: int, request: Request):
    """Revoke (deactivate) an API key."""
    user = current_user(request)
    pool = request.app.state.pool

    async with pool.acquire() as conn:
        result = await conn.execute(
            """
            UPDATE api_keys SET is_active = FALSE
            WHERE id = $1 AND is_active = TRUE
              AND user_id = (SELECT id FROM users WHERE username = $2)
            """,
            key_id,
            user["username"],
        )

        if result == "UPDATE 0":
            raise HTTPException(status_code=404, detail="Key no encontrada o ya revocada")

    client_ip = request.client.host if request.client else None
    await log_event(
        pool,
        "api_key_revoke",
        username=user["username"],
        ip=client_ip,
        detail={"key_id": key_id},
    )

    return {"detail": "Key revocada."}
