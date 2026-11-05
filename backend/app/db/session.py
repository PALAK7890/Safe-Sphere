"""
SafeSphere AI — Database Session & Engine Configuration
Async PostgreSQL + PostGIS connection management using SQLAlchemy 2.0.
"""

from __future__ import annotations

import logging
import os
from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import NullPool
from sqlalchemy import text

logger = logging.getLogger(__name__)

DEFAULT_DATABASE_URL = (
    "postgresql+asyncpg://safesphere:CHANGE_ME@localhost:5432/safesphere_db"
)

DATABASE_URL = os.getenv("DATABASE_URL", DEFAULT_DATABASE_URL)

# Ensure URL uses asyncpg driver if a standard postgresql:// URL is passed
if DATABASE_URL.startswith("postgresql://"):
    DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://", 1)

# In test environments or when requested, use NullPool to avoid event loop affinity conflicts
is_testing = os.getenv("TESTING", "false").lower() in ("true", "1") or os.getenv("PYTEST_CURRENT_TEST") is not None

engine_kwargs = {
    "echo": os.getenv("DEBUG", "false").lower() == "true",
    "pool_pre_ping": True,
}

if is_testing:
    engine_kwargs["poolclass"] = NullPool
else:
    engine_kwargs["pool_size"] = int(os.getenv("DB_POOL_SIZE", "10"))
    engine_kwargs["max_overflow"] = int(os.getenv("DB_MAX_OVERFLOW", "20"))

engine: AsyncEngine = create_async_engine(DATABASE_URL, **engine_kwargs)

async_session_factory = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency for yielding asynchronous database sessions."""
    async with async_session_factory() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def check_db_connection() -> bool:
    """Check whether the database is accessible and PostGIS is enabled."""
    try:
        async with engine.connect() as conn:
            result = await conn.execute(text("SELECT PostGIS_Version();"))
            version = result.scalar()
            logger.info("Database healthy. PostGIS version: %s", version)
            return True
    except Exception as exc:
        logger.error("Database health check failed: %s", exc)
        return False
