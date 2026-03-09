"""
Shadow USDCLP - REST API (FastAPI)
"""

import logging
import os
from contextlib import asynccontextmanager

import asyncpg
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

from auth import decode_token, seed_users_if_empty
from routes import shadow, correlations, model, config, auth as auth_routes, users as users_routes, price_ticks, audit_logs, api_keys, public, service_credentials

DATABASE_URL = os.environ["DATABASE_URL"]

# Comma-separated list of allowed origins, e.g. "https://shadow.buda.com,http://localhost:3000"
# Defaults to "*" for local dev; set explicitly in production.
_raw_origins = os.getenv("ALLOWED_ORIGINS", "*")
ALLOWED_ORIGINS = [o.strip() for o in _raw_origins.split(",")]

if "*" in ALLOWED_ORIGINS:
    logging.getLogger(__name__).warning(
        "CORS ALLOWED_ORIGINS contains '*' — all origins allowed. Set explicit origins for production."
    )

pool: asyncpg.Pool | None = None

# Paths that don't require a valid JWT
_PUBLIC_PATHS = {"/health", "/auth/login", "/docs", "/openapi.json", "/redoc"}
# Path prefixes that use their own auth (API key)
_APIKEY_PREFIXES = ("/api/v1/public/",)


class JWTAuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if request.url.path in _PUBLIC_PATHS:
            return await call_next(request)

        # API-key-authenticated routes handle their own auth
        if any(request.url.path.startswith(p) for p in _APIKEY_PREFIXES):
            return await call_next(request)

        header = request.headers.get("Authorization", "")
        if not header.startswith("Bearer "):
            return JSONResponse({"detail": "Not authenticated"}, status_code=401)

        token = header.split(" ", 1)[1]
        if decode_token(token) is None:
            return JSONResponse({"detail": "Invalid or expired token"}, status_code=401)

        return await call_next(request)


@asynccontextmanager
async def lifespan(app: FastAPI):
    global pool
    pool = await asyncpg.create_pool(DATABASE_URL, min_size=2, max_size=10)
    app.state.pool = pool
    await seed_users_if_empty(pool)
    yield
    await pool.close()


app = FastAPI(
    title="Shadow USDCLP API",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(JWTAuthMiddleware)

app.include_router(auth_routes.router)
app.include_router(shadow.router, prefix="/api/v1")
app.include_router(correlations.router, prefix="/api/v1")
app.include_router(model.router, prefix="/api/v1")
app.include_router(config.router, prefix="/api/v1")
app.include_router(price_ticks.router, prefix="/api/v1")
app.include_router(audit_logs.router, prefix="/api/v1")
app.include_router(api_keys.router)
app.include_router(public.router)
app.include_router(users_routes.router)
app.include_router(service_credentials.router)


@app.get("/health")
async def health():
    return {"status": "ok"}
