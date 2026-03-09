"""
CRUD endpoints for managing external service API keys (admin-only).

Credentials are encrypted at rest using Fernet symmetric encryption.
The plaintext value is never returned to the client — only a masked version.
"""

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from auth import current_user
from audit import log_event
import crypto

router = APIRouter(prefix="/api/v1/service-credentials", tags=["service-credentials"])

# Friendly display names for services
SERVICE_LABELS = {
    "twelvedata": "TwelveData",
    "cmf": "CMF Chile",
    "buda": "Buda.com",
}


def _require_admin(request: Request) -> dict:
    user = current_user(request)
    if user["role"] != "admin":
        raise HTTPException(status_code=403, detail="Admin required")
    return user


@router.get("")
async def list_credentials(request: Request):
    """List all service credentials with masked values."""
    _require_admin(request)

    if not crypto.is_configured():
        raise HTTPException(status_code=503, detail="Encryption not configured (CREDENTIAL_MASTER_KEY missing)")

    pool = request.app.state.pool
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT id, service_name, credential_key, encrypted_value, updated_at, updated_by "
            "FROM service_credentials ORDER BY service_name, credential_key"
        )

    result = []
    for r in rows:
        plaintext = ""
        if r["encrypted_value"]:
            try:
                plaintext = crypto.decrypt(r["encrypted_value"])
            except Exception:
                plaintext = ""

        result.append({
            "id": r["id"],
            "service_name": r["service_name"],
            "service_label": SERVICE_LABELS.get(r["service_name"], r["service_name"]),
            "credential_key": r["credential_key"],
            "masked_value": crypto.mask(plaintext) if plaintext else "",
            "is_set": bool(plaintext),
            "updated_at": r["updated_at"].isoformat() if r["updated_at"] else None,
            "updated_by": r["updated_by"],
        })

    return result


class CredentialUpdate(BaseModel):
    value: str


@router.put("/{service_name}/{credential_key}")
async def update_credential(service_name: str, credential_key: str, body: CredentialUpdate, request: Request):
    """Set or update an encrypted service credential."""
    user = _require_admin(request)

    if not crypto.is_configured():
        raise HTTPException(status_code=503, detail="Encryption not configured (CREDENTIAL_MASTER_KEY missing)")

    if not body.value.strip():
        raise HTTPException(status_code=400, detail="Value cannot be empty")

    pool = request.app.state.pool
    encrypted = crypto.encrypt(body.value.strip())

    async with pool.acquire() as conn:
        result = await conn.execute(
            "UPDATE service_credentials SET encrypted_value = $1, updated_at = NOW(), updated_by = $2 "
            "WHERE service_name = $3 AND credential_key = $4",
            encrypted, user["username"], service_name, credential_key,
        )

    if result == "UPDATE 0":
        raise HTTPException(status_code=404, detail=f"Credential {service_name}/{credential_key} not found")

    await log_event(
        pool, "service_credential_update",
        username=user["username"],
        ip=request.client.host if request.client else None,
        detail={"service_name": service_name, "credential_key": credential_key},
    )

    return {"ok": True, "service_name": service_name, "credential_key": credential_key}


@router.delete("/{service_name}/{credential_key}")
async def clear_credential(service_name: str, credential_key: str, request: Request):
    """Clear a service credential (set to empty)."""
    user = _require_admin(request)

    pool = request.app.state.pool
    async with pool.acquire() as conn:
        result = await conn.execute(
            "UPDATE service_credentials SET encrypted_value = '', updated_at = NOW(), updated_by = $1 "
            "WHERE service_name = $2 AND credential_key = $3",
            user["username"], service_name, credential_key,
        )

    if result == "UPDATE 0":
        raise HTTPException(status_code=404, detail=f"Credential {service_name}/{credential_key} not found")

    await log_event(
        pool, "service_credential_clear",
        username=user["username"],
        ip=request.client.host if request.client else None,
        detail={"service_name": service_name, "credential_key": credential_key},
    )

    return {"ok": True, "service_name": service_name, "credential_key": credential_key}
