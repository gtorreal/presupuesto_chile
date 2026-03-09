"""
Read and decrypt service credentials from the database.

On first startup, seeds DB from env vars if credentials are empty.
After that, DB values take priority over env vars.
"""

import logging
import os

import asyncpg

logger = logging.getLogger(__name__)

_MASTER_KEY = os.environ.get("CREDENTIAL_MASTER_KEY", "")
_fernet = None

if _MASTER_KEY:
    try:
        from cryptography.fernet import Fernet
        _fernet = Fernet(_MASTER_KEY.encode())
    except Exception as e:
        logger.error("Failed to initialize Fernet: %s", e)

# Map (service_name, credential_key) -> env var name for fallback/seeding
ENV_VAR_MAP = {
    ("twelvedata", "api_key"): "TWELVEDATA_API_KEY",
    ("cmf", "api_key"): "CMF_API_KEY",
    ("buda", "api_key"): "BUDA_API_KEY",
    ("buda", "api_secret"): "BUDA_API_SECRET",
}


def _decrypt(ciphertext: str) -> str:
    if not ciphertext or not _fernet:
        return ""
    try:
        return _fernet.decrypt(ciphertext.encode()).decode()
    except Exception:
        return ""


def _encrypt(plaintext: str) -> str:
    if not _fernet:
        return ""
    return _fernet.encrypt(plaintext.encode()).decode()


async def seed_from_env(pool: asyncpg.Pool) -> None:
    """One-time seed: if a DB credential is empty but env var has a value, store it encrypted."""
    if not _fernet:
        logger.info("credential_store: no CREDENTIAL_MASTER_KEY, skipping DB seed")
        return

    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT service_name, credential_key, encrypted_value FROM service_credentials"
        )

    existing = {(r["service_name"], r["credential_key"]): r["encrypted_value"] for r in rows}

    for (svc, key), env_var in ENV_VAR_MAP.items():
        current = existing.get((svc, key), "")
        if current:
            continue  # already has a value in DB
        env_val = os.environ.get(env_var, "").strip()
        if not env_val:
            continue  # env var also empty

        encrypted = _encrypt(env_val)
        async with pool.acquire() as conn:
            await conn.execute(
                "UPDATE service_credentials SET encrypted_value = $1, updated_at = NOW(), updated_by = 'env_seed' "
                "WHERE service_name = $2 AND credential_key = $3",
                encrypted, svc, key,
            )
        logger.info("credential_store: seeded %s/%s from env var %s", svc, key, env_var)


async def get_all_credentials(pool: asyncpg.Pool) -> dict[tuple[str, str], str]:
    """
    Read all credentials from DB, decrypt, and return as dict.
    Falls back to env vars if DB value is empty or encryption is not configured.
    Returns: {("service_name", "credential_key"): "plaintext_value", ...}
    """
    result: dict[tuple[str, str], str] = {}

    if _fernet:
        try:
            async with pool.acquire() as conn:
                rows = await conn.fetch(
                    "SELECT service_name, credential_key, encrypted_value FROM service_credentials"
                )
            for r in rows:
                val = _decrypt(r["encrypted_value"])
                if val:
                    result[(r["service_name"], r["credential_key"])] = val
        except Exception as e:
            logger.warning("credential_store: DB read failed, using env vars: %s", e)

    # Fill in missing values from env vars
    for (svc, key), env_var in ENV_VAR_MAP.items():
        if (svc, key) not in result:
            env_val = os.environ.get(env_var, "").strip()
            if env_val:
                result[(svc, key)] = env_val

    return result
