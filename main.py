from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse
from contextlib import asynccontextmanager
from pathlib import Path
import logging
import aiosqlite

from app.core.config import settings
from app.core.database import create_tables
from app.api.v1.router import api_router
from app.utils.seed import seed_initial_data

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def run_migrations():
    db_path = settings.DATABASE_URL.replace("sqlite+aiosqlite:///", "").replace("sqlite:///", "")
    async with aiosqlite.connect(db_path) as db:
        try:
            await db.execute("ALTER TABLE users ADD COLUMN email_verified BOOLEAN NOT NULL DEFAULT 1")
            await db.commit()
            logger.info("Migration: added email_verified column")
        except Exception:
            pass  # column already exists


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info(f"Starting {settings.APP_NAME} v{settings.APP_VERSION}")
    await create_tables()
    await run_migrations()
    await seed_initial_data()
    Path(settings.LOCAL_STORAGE_PATH).mkdir(parents=True, exist_ok=True)
    yield
    logger.info("Shutting down...")


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="Professional Life Management System API",
    docs_url="/docs" if settings.DEBUG else None,
    redoc_url="/redoc" if settings.DEBUG else None,
    lifespan=lifespan,
)

_origins = settings.ALLOWED_ORIGINS
_allow_all = "*" in _origins
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"] if _allow_all else _origins,
    allow_credentials=not _allow_all,
    allow_methods=["*"],
    allow_headers=["*"],
)

storage_path = Path(settings.LOCAL_STORAGE_PATH)
storage_path.mkdir(parents=True, exist_ok=True)
app.mount("/storage", StaticFiles(directory=str(storage_path)), name="storage")

app.include_router(api_router)


@app.get("/")
async def root():
    return {"app": settings.APP_NAME, "version": settings.APP_VERSION, "status": "running"}


@app.get("/health")
async def health():
    return {"status": "healthy", "version": settings.APP_VERSION}
