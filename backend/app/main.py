from contextlib import asynccontextmanager

import psycopg
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup — placeholder for Phase 2 (DB engine, etc.)
    yield
    # Shutdown


app = FastAPI(title="Sea Breeze Analog", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)


def _get_psycopg_dsn() -> str:
    """Strip the '+psycopg' dialect suffix so psycopg.connect gets a plain postgresql:// DSN."""
    return settings.database_url.replace("+psycopg", "")


@app.get("/api/health")
def health():
    try:
        dsn = _get_psycopg_dsn()
        with psycopg.connect(dsn, connect_timeout=3) as conn:
            conn.execute("SELECT 1")
        db_status = "connected"
        status = "healthy"
    except Exception:
        db_status = "disconnected"
        status = "degraded"

    return {
        "status": status,
        "database": db_status,
        "environment": settings.app_env,
    }
