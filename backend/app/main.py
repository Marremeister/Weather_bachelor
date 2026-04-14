from contextlib import asynccontextmanager
from pathlib import Path

import psycopg
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import select

from app.config import settings
from app.database import SessionLocal
from app.models.location import Location
from app.routers import analysis, classification, library, locations, weather

STATIC_DIR = Path(__file__).resolve().parent.parent / "static"


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

# Dynamic CORS origins from settings
origins = [o.strip() for o in settings.allowed_origins.split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(locations.router)
app.include_router(weather.router)
app.include_router(classification.router)
app.include_router(analysis.router)
app.include_router(library.router)


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


# --- Production static file serving ---
# The static/ dir only exists inside the production Docker image.
if STATIC_DIR.is_dir():
    # Serve Vite-built assets (JS, CSS, images)
    app.mount("/assets", StaticFiles(directory=STATIC_DIR / "assets"), name="assets")

    @app.get("/{full_path:path}")
    async def spa_fallback(full_path: str):
        """Serve index.html for any non-API route (SPA client-side routing)."""
        file = STATIC_DIR / full_path
        if file.is_file():
            return FileResponse(file)
        return FileResponse(STATIC_DIR / "index.html")
