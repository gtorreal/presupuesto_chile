"""
Audit log query endpoint (admin only).
"""

from fastapi import APIRouter, HTTPException, Request

from auth import decode_token

router = APIRouter()


def _require_admin(request: Request) -> dict:
    token = request.headers.get("Authorization", "").split(" ", 1)[-1]
    user = decode_token(token)
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    if user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin required")
    return user


@router.get("/audit-logs")
async def get_audit_logs(
    request: Request,
    limit: int = 100,
    offset: int = 0,
    username: str | None = None,
    action: str | None = None,
):
    """Return audit log entries, newest first. Admin only."""
    _require_admin(request)

    if limit > 500:
        limit = 500

    pool = request.app.state.pool

    conditions = []
    params = []
    idx = 1

    if username:
        conditions.append(f"username = ${idx}")
        params.append(username)
        idx += 1
    if action:
        conditions.append(f"action = ${idx}")
        params.append(action)
        idx += 1

    where = f"WHERE {' AND '.join(conditions)}" if conditions else ""

    async with pool.acquire() as conn:
        rows = await conn.fetch(
            f"""
            SELECT id, ts, username, action, detail, ip
            FROM audit_log
            {where}
            ORDER BY ts DESC
            LIMIT ${idx} OFFSET ${idx + 1}
            """,
            *params,
            limit,
            offset,
        )
        total = await conn.fetchval(
            f"SELECT COUNT(*) FROM audit_log {where}",
            *params,
        )

    return {
        "total": total,
        "items": [
            {
                "id": r["id"],
                "ts": r["ts"].isoformat(),
                "username": r["username"],
                "action": r["action"],
                "detail": r["detail"] if r["detail"] else None,
                "ip": r["ip"],
            }
            for r in rows
        ],
    }
