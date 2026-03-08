"""
Audit logging helper.

Usage:
    from audit import log_event
    await log_event(pool, "password_change", username="admin", ip="1.2.3.4", detail={"target": "admin"})
"""

import json

import asyncpg


async def log_event(
    pool: asyncpg.Pool,
    action: str,
    *,
    username: str | None = None,
    ip: str | None = None,
    detail: dict | None = None,
) -> None:
    """Insert one row into audit_log. Fire-and-forget safe."""
    async with pool.acquire() as conn:
        await conn.execute(
            "INSERT INTO audit_log (username, action, detail, ip) VALUES ($1, $2, $3::jsonb, $4)",
            username,
            action,
            json.dumps(detail) if detail else None,
            ip,
        )
