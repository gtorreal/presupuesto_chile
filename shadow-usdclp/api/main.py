"""
Shadow USDCLP - REST API (FastAPI)
"""

import os
from contextlib import asynccontextmanager

import asyncpg
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

from auth import decode_token
from routes import shadow, correlations, model, config, auth as auth_routes

DATABASE_URL = os.environ["DATABASE_URL"]

pool: asyncpg.Pool | None = None

# Paths that don't require a valid JWT
_PUBLIC_PATHS = {"/health", "/auth/login"}


class JWTAuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if request.url.path in _PUBLIC_PATHS:
            return await call_next(request)

        header = request.headers.get("Authorization", "")
        if not header.startswith("Bearer "):
            return JSONResponse({"detail": "Not authenticated"}, status_code=401)

        token = header.split(" ", 1)[1]
        if not decode_token(token):
            return JSONResponse({"detail": "Invalid or expired token"}, status_code=401)

        return await call_next(request)


@asynccontextmanager
async def lifespan(app: FastAPI):
    global pool
    pool = await asyncpg.create_pool(DATABASE_URL, min_size=2, max_size=10)
    app.state.pool = pool
    yield
    await pool.close()


app = FastAPI(
    title="Shadow USDCLP API",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(JWTAuthMiddleware)

app.include_router(auth_routes.router)
app.include_router(shadow.router, prefix="/api/v1")
app.include_router(correlations.router, prefix="/api/v1")
app.include_router(model.router, prefix="/api/v1")
app.include_router(config.router, prefix="/api/v1")


@app.get("/health")
async def health():
    return {"status": "ok"}
