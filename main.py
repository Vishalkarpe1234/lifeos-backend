from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse
from contextlib import asynccontextmanager
from pathlib import Path
import logging

from app.core.config import settings
from app.core.database import create_tables, engine
from app.api.v1.router import api_router
from app.utils.seed import seed_initial_data
from sqlalchemy import text

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def run_migrations():
    is_sqlite = "sqlite" in str(engine.url)
    default_val = "1" if is_sqlite else "TRUE"
    try:
        async with engine.begin() as conn:
            await conn.execute(text(f"ALTER TABLE users ADD COLUMN email_verified BOOLEAN NOT NULL DEFAULT {default_val}"))
            logger.info("Migration: added email_verified column")
    except Exception:
        pass  # column already exists or create_all already included it

    try:
        async with engine.begin() as conn:
            await conn.execute(text("ALTER TABLE notes ADD COLUMN user_id INTEGER REFERENCES users(id)"))
    except Exception:
        pass

    try:
        async with engine.begin() as conn:
            await conn.execute(text("ALTER TABLE users ADD COLUMN location_permission BOOLEAN DEFAULT FALSE"))
    except Exception:
        pass

    try:
        async with engine.begin() as conn:
            is_sqlite = "sqlite" in str(engine.url)
            if is_sqlite:
                await conn.execute(text("""
                    CREATE TABLE IF NOT EXISTS user_locations (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                        latitude REAL NOT NULL,
                        longitude REAL NOT NULL,
                        accuracy REAL,
                        timestamp TEXT NOT NULL,
                        created_at TEXT DEFAULT (datetime('now'))
                    )
                """))
            else:
                await conn.execute(text("""
                    CREATE TABLE IF NOT EXISTS user_locations (
                        id SERIAL PRIMARY KEY,
                        user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                        latitude DOUBLE PRECISION NOT NULL,
                        longitude DOUBLE PRECISION NOT NULL,
                        accuracy DOUBLE PRECISION,
                        timestamp TIMESTAMPTZ NOT NULL,
                        created_at TIMESTAMPTZ DEFAULT NOW()
                    )
                """))
    except Exception:
        pass

    try:
        async with engine.begin() as conn:
            await conn.execute(text("ALTER TABLE users ADD COLUMN username VARCHAR(50)"))
    except Exception:
        pass

    try:
        async with engine.begin() as conn:
            await conn.execute(text("CREATE UNIQUE INDEX IF NOT EXISTS ix_users_username ON users (username)"))
    except Exception:
        pass

    try:
        async with engine.begin() as conn:
            is_sqlite = "sqlite" in str(engine.url)
            if is_sqlite:
                await conn.execute(text("""
                    CREATE TABLE IF NOT EXISTS friend_requests (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        sender_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                        receiver_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                        status VARCHAR(20) NOT NULL DEFAULT 'pending',
                        created_at TEXT DEFAULT (datetime('now')),
                        updated_at TEXT DEFAULT (datetime('now'))
                    )
                """))
                await conn.execute(text("""
                    CREATE TABLE IF NOT EXISTS friendships (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        user1_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                        user2_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                        created_at TEXT DEFAULT (datetime('now')),
                        updated_at TEXT DEFAULT (datetime('now'))
                    )
                """))
                await conn.execute(text("""
                    CREATE TABLE IF NOT EXISTS messages (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        sender_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                        receiver_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                        content TEXT,
                        file_url VARCHAR(500),
                        file_type VARCHAR(50),
                        timestamp TEXT DEFAULT (datetime('now')),
                        deleted_by_sender BOOLEAN NOT NULL DEFAULT 0,
                        deleted_by_receiver BOOLEAN NOT NULL DEFAULT 0
                    )
                """))
            else:
                await conn.execute(text("""
                    CREATE TABLE IF NOT EXISTS friend_requests (
                        id SERIAL PRIMARY KEY,
                        sender_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                        receiver_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                        status VARCHAR(20) NOT NULL DEFAULT 'pending',
                        created_at TIMESTAMPTZ DEFAULT NOW(),
                        updated_at TIMESTAMPTZ DEFAULT NOW()
                    )
                """))
                await conn.execute(text("""
                    CREATE TABLE IF NOT EXISTS friendships (
                        id SERIAL PRIMARY KEY,
                        user1_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                        user2_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                        created_at TIMESTAMPTZ DEFAULT NOW(),
                        updated_at TIMESTAMPTZ DEFAULT NOW()
                    )
                """))
                await conn.execute(text("""
                    CREATE TABLE IF NOT EXISTS messages (
                        id SERIAL PRIMARY KEY,
                        sender_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                        receiver_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                        content TEXT,
                        file_url VARCHAR(500),
                        file_type VARCHAR(50),
                        timestamp TIMESTAMPTZ DEFAULT NOW(),
                        deleted_by_sender BOOLEAN NOT NULL DEFAULT FALSE,
                        deleted_by_receiver BOOLEAN NOT NULL DEFAULT FALSE
                    )
                """))
    except Exception:
        pass


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info(f"Starting {settings.APP_NAME} v{settings.APP_VERSION}")
    try:
        await create_tables()
    except Exception as e:
        logger.error(f"create_tables error (non-fatal): {e}")
    try:
        await run_migrations()
    except Exception as e:
        logger.error(f"run_migrations error (non-fatal): {e}")
    try:
        await seed_initial_data()
    except Exception as e:
        logger.error(f"seed error (non-fatal): {e}")
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


@app.get("/db-health")
async def db_health():
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        return {"status": "ok", "db": "connected"}
    except Exception as e:
        return JSONResponse(status_code=503, content={"status": "error", "db": str(e)[:100]})
