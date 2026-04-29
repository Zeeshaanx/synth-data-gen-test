"""
PostgreSQL persistence layer.
All job writes go here IN ADDITION to the in-memory JOB_STORE so the
existing code keeps working without any changes if the DB is unreachable.
"""

import os
import json
import logging
import asyncio
from typing import Optional, List, Dict, Any

log = logging.getLogger(__name__)

# ── optional import: asyncpg only needed when DB is configured ──────────────
try:
    import asyncpg
    HAS_ASYNCPG = True
except ImportError:
    HAS_ASYNCPG = False
    log.warning("asyncpg not installed – PostgreSQL persistence disabled")

DATABASE_URL: Optional[str] = os.environ.get("DATABASE_URL")  # injected by systemd

_pool: Optional[Any] = None


# ────────────────────────────────────────────────────────────────────────────
# Pool lifecycle
# ────────────────────────────────────────────────────────────────────────────

async def init_pool() -> None:
    """Call once at FastAPI startup."""
    global _pool
    if not HAS_ASYNCPG or not DATABASE_URL:
        log.warning("DB persistence disabled (no DATABASE_URL or asyncpg missing)")
        return
    try:
        _pool = await asyncpg.create_pool(
            DATABASE_URL,
            min_size=2,
            max_size=10,
            command_timeout=30,
        )
        await _create_schema()
        log.info("PostgreSQL pool ready")
    except Exception as exc:
        log.error(f"Could not connect to PostgreSQL: {exc} — running in memory-only mode")
        _pool = None


async def close_pool() -> None:
    global _pool
    if _pool:
        await _pool.close()
        _pool = None


async def _create_schema() -> None:
    async with _pool.acquire() as conn:
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS jobs (
                id              BIGSERIAL PRIMARY KEY,
                job_id          TEXT        NOT NULL UNIQUE,
                job_type        TEXT        NOT NULL DEFAULT 'create',
                status          TEXT        NOT NULL DEFAULT 'processing',
                model_provider  TEXT,
                model_id        TEXT,
                num_records     INTEGER,
                generate_request JSONB,
                result          JSONB,
                error_message   TEXT,
                csv_filename    TEXT,
                created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
            );
            CREATE INDEX IF NOT EXISTS idx_jobs_job_id  ON jobs(job_id);
            CREATE INDEX IF NOT EXISTS idx_jobs_status  ON jobs(status);
            CREATE INDEX IF NOT EXISTS idx_jobs_created ON jobs(created_at DESC);
        """)


# ────────────────────────────────────────────────────────────────────────────
# Helpers – all silently no-op when pool is None
# ────────────────────────────────────────────────────────────────────────────

def _safe(coro):
    """Fire-and-forget a coroutine; swallow exceptions so in-mem path never breaks."""
    async def _run():
        try:
            await coro
        except Exception as exc:
            log.error(f"DB write error (non-fatal): {exc}")
    asyncio.ensure_future(_run())


# ────────────────────────────────────────────────────────────────────────────
# Public API – called from routes / job_controller
# ────────────────────────────────────────────────────────────────────────────

def insert_job(
    job_id: str,
    job_type: str,
    generate_request: dict,
    model_provider: str,
    model_id: str,
    num_records: int,
) -> None:
    """Non-blocking insert – safe to call from sync route handlers."""
    if not _pool:
        return
    _safe(_insert_job(job_id, job_type, generate_request, model_provider, model_id, num_records))


async def _insert_job(job_id, job_type, generate_request, model_provider, model_id, num_records):
    async with _pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO jobs
                (job_id, job_type, status, model_provider, model_id,
                 num_records, generate_request)
            VALUES ($1,$2,'processing',$3,$4,$5,$6::jsonb)
            ON CONFLICT (job_id) DO NOTHING
            """,
            job_id, job_type, model_provider, model_id, num_records,
            json.dumps(generate_request),
        )


def update_job_completed(job_id: str, result: dict, csv_filename: str) -> None:
    if not _pool:
        return
    _safe(_update_job_completed(job_id, result, csv_filename))


async def _update_job_completed(job_id, result, csv_filename):
    async with _pool.acquire() as conn:
        await conn.execute(
            """
            UPDATE jobs
            SET status='completed', result=$2::jsonb,
                csv_filename=$3, updated_at=NOW()
            WHERE job_id=$1
            """,
            job_id, json.dumps(result), csv_filename,
        )


def update_job_failed(job_id: str, error: str) -> None:
    if not _pool:
        return
    _safe(_update_job_failed(job_id, error))


async def _update_job_failed(job_id, error):
    async with _pool.acquire() as conn:
        await conn.execute(
            """
            UPDATE jobs
            SET status='failed', error_message=$2, updated_at=NOW()
            WHERE job_id=$1
            """,
            job_id, error,
        )


# ────────────────────────────────────────────────────────────────────────────
# Read – used by the /jobs UI page
# ────────────────────────────────────────────────────────────────────────────

async def list_jobs(limit: int = 200) -> List[Dict[str, Any]]:
    """Returns jobs newest-first. Falls back to [] when DB unavailable."""
    if not _pool:
        return []
    async with _pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT job_id, job_type, status, model_provider, model_id,
                   num_records, csv_filename, error_message,
                   created_at, updated_at,
                   result->>'duration_seconds' AS duration_seconds
            FROM jobs
            ORDER BY created_at DESC
            LIMIT $1
            """,
            limit,
        )
    return [dict(r) for r in rows]


async def get_job(job_id: str) -> Optional[Dict[str, Any]]:
    """Full job row including result JSON."""
    if not _pool:
        return None
    async with _pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT * FROM jobs WHERE job_id=$1", job_id
        )
    return dict(row) if row else None
