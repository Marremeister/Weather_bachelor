from contextlib import asynccontextmanager

import psycopg
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select

from app.config import settings
from app.database import SessionLocal
from app.models.location import Location
from app.routers import locations


def _seed_default_location() -> None:
    """Insert the default LA / San Pedro location if it doesn't already exist."""
    with SessionLocal() as db:
        exists = db.execute(
            select(Location).where(Location.name == "Los Angeles / San Pedro")
        ).scalar_one_or_none()
        if exists is None:
            db.add(
                Location(
                    name="Los Angeles / San Pedro",
                    latitude=33.708965,
                    longitude=-118.268343,
                    timezone="America/Los_Angeles",
                )
            )
            db.commit()


@asynccontextmanager
async def lifespan(app: FastAPI):
    _seed_default_location()
    yield


app = FastAPI(title="Sea Breeze Analog", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:5174"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(locations.router)


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
