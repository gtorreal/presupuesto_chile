"""
Auth utilities: JWT creation/verification + user store from env vars.

Configure users via AUTH_USERS env var:
  Single user:   AUTH_USERS=admin:mypassword
  Multiple:      AUTH_USERS=admin:pass1,analyst:pass2

JWT secret via JWT_SECRET (generate with: openssl rand -hex 32)
Token expiry via JWT_EXPIRE_HOURS (default: 8)
"""

import os
from datetime import datetime, timedelta, timezone
from typing import Optional

from jose import JWTError, jwt
from passlib.context import CryptContext

SECRET_KEY = os.environ.get("JWT_SECRET", "insecure-default-change-in-production")
ALGORITHM = "HS256"
EXPIRE_HOURS = int(os.environ.get("JWT_EXPIRE_HOURS", "8"))

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def _load_users() -> dict[str, str]:
    """Parse AUTH_USERS env var and return {username: bcrypt_hash}."""
    raw = os.environ.get("AUTH_USERS", "admin:shadow")
    users = {}
    for entry in raw.split(","):
        parts = entry.strip().split(":", 1)
        if len(parts) == 2:
            username, password = parts[0].strip(), parts[1].strip()
            if username:
                users[username] = pwd_context.hash(password)
    return users


# Hashed at startup — plain-text passwords only live in env vars
USERS: dict[str, str] = _load_users()


def authenticate_user(username: str, password: str) -> bool:
    hashed = USERS.get(username)
    if not hashed:
        return False
    return pwd_context.verify(password, hashed)


def create_access_token(username: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(hours=EXPIRE_HOURS)
    payload = {"sub": username, "exp": expire}
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def decode_token(token: str) -> Optional[str]:
    """Return username if token is valid, None otherwise."""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload.get("sub")
    except JWTError:
        return None
