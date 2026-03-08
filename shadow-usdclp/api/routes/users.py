"""
User management + OTP setup endpoints.

All routes require a valid JWT (enforced by JWTAuthMiddleware in main.py).
User-management routes (list/create/delete) additionally require the 'admin' role.
"""

from fastapi import APIRouter, HTTPException, Request, status
from pydantic import BaseModel, Field

from auth import (
    decode_token,
    generate_totp_secret,
    get_totp_provisioning_uri,
    hash_password,
    verify_password,
    verify_totp,
)
from audit import log_event

router = APIRouter(prefix="/api/v1/users")


# --- Dependency helpers ---

def _current_user(request: Request) -> dict:
    token = request.headers.get("Authorization", "").split(" ", 1)[-1]
    user = decode_token(token)
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return user


def _require_admin(request: Request) -> dict:
    user = _current_user(request)
    if user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin required")
    return user


def _client_ip(request: Request) -> str | None:
    return request.client.host if request.client else None


# --- Pydantic models ---

class CreateUserRequest(BaseModel):
    username: str = Field(..., min_length=2, max_length=50)
    password: str = Field(..., min_length=6)
    role: str = "admin"


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str = Field(..., min_length=6)


class OtpVerifyRequest(BaseModel):
    code: str


# --- Current user endpoints ---

@router.get("/me")
async def get_me(request: Request):
    current = _current_user(request)
    pool = request.app.state.pool
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT username, role, otp_enabled, created_at FROM users WHERE username = $1",
            current["username"],
        )
    return dict(row)


@router.post("/me/change-password")
async def change_password(body: ChangePasswordRequest, request: Request):
    current = _current_user(request)
    pool = request.app.state.pool
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT password_hash FROM users WHERE username = $1",
            current["username"],
        )
        if not verify_password(body.current_password, row["password_hash"]):
            raise HTTPException(status_code=400, detail="Current password is incorrect")
        await conn.execute(
            "UPDATE users SET password_hash = $1 WHERE username = $2",
            hash_password(body.new_password),
            current["username"],
        )
    await log_event(pool, "password_change", username=current["username"], ip=_client_ip(request))
    return {"success": True}


# --- OTP setup ---

@router.post("/me/otp-setup")
async def otp_setup(request: Request):
    """Generate a new TOTP secret and save it as pending. Returns QR URI."""
    current = _current_user(request)
    secret = generate_totp_secret()
    uri = get_totp_provisioning_uri(secret, current["username"])
    pool = request.app.state.pool
    async with pool.acquire() as conn:
        await conn.execute(
            "UPDATE users SET otp_pending_secret = $1 WHERE username = $2",
            secret,
            current["username"],
        )
    await log_event(pool, "otp_setup", username=current["username"], ip=_client_ip(request))
    return {"secret": secret, "uri": uri}


@router.post("/me/otp-enable")
async def otp_enable(body: OtpVerifyRequest, request: Request):
    """Verify OTP code against the pending secret, then activate OTP."""
    current = _current_user(request)
    pool = request.app.state.pool
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT otp_pending_secret FROM users WHERE username = $1",
            current["username"],
        )
        if not row or not row["otp_pending_secret"]:
            raise HTTPException(status_code=400, detail="No OTP setup in progress. Call /me/otp-setup first.")
        if not verify_totp(row["otp_pending_secret"], body.code):
            raise HTTPException(status_code=400, detail="Invalid OTP code")
        await conn.execute(
            """
            UPDATE users
            SET otp_enabled = TRUE,
                otp_secret = otp_pending_secret,
                otp_pending_secret = NULL
            WHERE username = $1
            """,
            current["username"],
        )
    await log_event(pool, "otp_enable", username=current["username"], ip=_client_ip(request))
    return {"success": True}


@router.post("/me/otp-disable")
async def otp_disable(body: OtpVerifyRequest, request: Request):
    """Disable OTP (requires a current valid OTP code as confirmation)."""
    current = _current_user(request)
    pool = request.app.state.pool
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT otp_secret FROM users WHERE username = $1 AND otp_enabled = TRUE",
            current["username"],
        )
        if not row:
            raise HTTPException(status_code=400, detail="OTP is not enabled for this account")
        if not verify_totp(row["otp_secret"], body.code):
            raise HTTPException(status_code=400, detail="Invalid OTP code")
        await conn.execute(
            "UPDATE users SET otp_enabled = FALSE, otp_secret = NULL WHERE username = $1",
            current["username"],
        )
    await log_event(pool, "otp_disable", username=current["username"], ip=_client_ip(request))
    return {"success": True}


# --- Admin: user management ---

@router.get("")
async def list_users(request: Request):
    _require_admin(request)
    pool = request.app.state.pool
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT username, role, otp_enabled, created_at, is_active FROM users ORDER BY created_at"
        )
    return [dict(r) for r in rows]


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_user(body: CreateUserRequest, request: Request):
    _require_admin(request)
    pool = request.app.state.pool
    async with pool.acquire() as conn:
        existing = await conn.fetchval(
            "SELECT 1 FROM users WHERE username = $1", body.username
        )
        if existing:
            raise HTTPException(status_code=409, detail="Username already exists")
        await conn.execute(
            "INSERT INTO users (username, password_hash, role) VALUES ($1, $2, $3)",
            body.username,
            hash_password(body.password),
            body.role,
        )
    current = _current_user(request)
    await log_event(
        pool, "user_create",
        username=current["username"],
        ip=_client_ip(request),
        detail={"target": body.username, "role": body.role},
    )
    return {"username": body.username, "role": body.role}


@router.delete("/{username}")
async def delete_user(username: str, request: Request):
    current = _require_admin(request)
    if current["username"] == username:
        raise HTTPException(status_code=400, detail="Cannot delete your own account")
    pool = request.app.state.pool
    async with pool.acquire() as conn:
        result = await conn.execute("DELETE FROM users WHERE username = $1", username)
        if result == "DELETE 0":
            raise HTTPException(status_code=404, detail="User not found")
    await log_event(
        pool, "user_delete",
        username=current["username"],
        ip=_client_ip(request),
        detail={"target": username},
    )
    return {"success": True}
