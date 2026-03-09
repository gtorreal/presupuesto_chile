"""
Auth utilities: JWT creation/verification + TOTP helpers.

Users are stored in the `users` DB table (DB-backed auth).
On first startup with an empty table, seeds from AUTH_USERS env var:
  AUTH_USERS=admin:mypassword  (or comma-separated: admin:pass1,analyst:pass2)

JWT secret via JWT_SECRET (generate with: openssl rand -hex 32)
Token expiry via JWT_EXPIRE_HOURS (default: 8)
"""

import hashlib
import os
from datetime import datetime, timedelta, timezone
from typing import Optional

import pyotp
from fastapi import HTTPException, Request
import jwt
from passlib.context import CryptContext

SECRET_KEY = os.environ["JWT_SECRET"]  # Required — no insecure fallback
ALGORITHM = "HS256"
EXPIRE_HOURS = int(os.environ.get("JWT_EXPIRE_HOURS", "8"))

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


# --- Password helpers ---

def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(password: str, hashed: str) -> bool:
    return pwd_context.verify(password, hashed)


def hash_api_key(key: str) -> str:
    """SHA-256 hash for API key storage/lookup."""
    return hashlib.sha256(key.encode()).hexdigest()


# --- JWT ---

def create_access_token(username: str, role: str = "admin") -> str:
    expire = datetime.now(timezone.utc) + timedelta(hours=EXPIRE_HOURS)
    payload = {"sub": username, "role": role, "exp": expire}
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)  # PyJWT returns str


def decode_token(token: str) -> Optional[dict]:
    """Return {"username": ..., "role": ...} if valid, None otherwise."""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username = payload.get("sub")
        if not username:
            return None
        return {"username": username, "role": payload.get("role", "admin")}
    except jwt.InvalidTokenError:
        return None


def current_user(request: Request) -> dict:
    """Extract and validate JWT from request. Returns {"username": ..., "role": ...}."""
    header = request.headers.get("Authorization", "")
    if not header.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Not authenticated")
    token = header.split(" ", 1)[1]
    user = decode_token(token)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    return user


# --- TOTP helpers ---

def generate_totp_secret() -> str:
    return pyotp.random_base32()


def get_totp_provisioning_uri(secret: str, username: str) -> str:
    return pyotp.TOTP(secret).provisioning_uri(
        name=username,
        issuer_name="Shadow USDCLP",
    )


def verify_totp(secret: str, code: str) -> bool:
    return pyotp.TOTP(secret).verify(code, valid_window=1)


# --- Startup seed ---

async def seed_users_if_empty(pool) -> None:
    """If the users table is empty, seed from AUTH_USERS env var."""
    async with pool.acquire() as conn:
        count = await conn.fetchval("SELECT COUNT(*) FROM users")
        if count > 0:
            return

        raw = os.environ.get("AUTH_USERS", "admin:shadow")
        for entry in raw.split(","):
            parts = entry.strip().split(":", 1)
            if len(parts) == 2:
                username, password = parts[0].strip(), parts[1].strip()
                if username:
                    await conn.execute(
                        """
                        INSERT INTO users (username, password_hash, role)
                        VALUES ($1, $2, 'admin')
                        ON CONFLICT DO NOTHING
                        """,
                        username,
                        hash_password(password),
                    )
