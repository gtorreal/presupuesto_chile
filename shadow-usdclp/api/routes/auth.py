from collections import defaultdict
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, HTTPException, Request, status
from pydantic import BaseModel

from auth import create_access_token, verify_password, verify_totp
from audit import log_event

router = APIRouter()

# In-memory brute-force protection: track failed attempts per (ip, username).
# Lockout after _MAX_ATTEMPTS failures within _WINDOW_SECONDS.
_MAX_ATTEMPTS = 10
_WINDOW_SECONDS = 300   # 5 minutes
_LOCKOUT_SECONDS = 300  # 5 minutes

# key → list of failure timestamps
_failures: dict[str, list[float]] = defaultdict(list)


def _rate_limit_key(request: Request, username: str) -> str:
    ip = request.client.host if request.client else "unknown"
    return f"{ip}:{username}"


def _check_rate_limit(key: str) -> None:
    now = datetime.now(timezone.utc).timestamp()
    timestamps = _failures[key]

    # Drop entries outside the window
    _failures[key] = [t for t in timestamps if now - t < _WINDOW_SECONDS]

    if len(_failures[key]) >= _MAX_ATTEMPTS:
        retry_after = int(_LOCKOUT_SECONDS - (now - _failures[key][0]))
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Too many failed attempts. Try again in {retry_after}s.",
            headers={"Retry-After": str(retry_after)},
        )


def _record_failure(key: str) -> None:
    _failures[key].append(datetime.now(timezone.utc).timestamp())


def _clear_failures(key: str) -> None:
    _failures.pop(key, None)


class LoginRequest(BaseModel):
    username: str
    password: str
    otp_code: Optional[str] = None


@router.post("/auth/login")
async def login(body: LoginRequest, request: Request):
    key = _rate_limit_key(request, body.username)
    _check_rate_limit(key)

    pool = request.app.state.pool
    async with pool.acquire() as conn:
        user = await conn.fetchrow(
            """
            SELECT username, password_hash, role, otp_enabled, otp_secret
            FROM users
            WHERE username = $1 AND is_active = TRUE
            """,
            body.username,
        )

    ip = request.client.host if request.client else None

    if not user or not verify_password(body.password, user["password_hash"]):
        _record_failure(key)
        await log_event(pool, "login_failed", username=body.username, ip=ip)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
        )

    if user["otp_enabled"]:
        if not body.otp_code:
            # Signal the frontend to show the OTP input
            return {"requires_otp": True}
        if not verify_totp(user["otp_secret"], body.otp_code):
            _record_failure(key)
            await log_event(pool, "login_failed_otp", username=body.username, ip=ip)
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid OTP code",
            )

    _clear_failures(key)
    await log_event(pool, "login", username=body.username, ip=ip)
    token = create_access_token(body.username, user["role"])
    return {"access_token": token, "token_type": "bearer"}
