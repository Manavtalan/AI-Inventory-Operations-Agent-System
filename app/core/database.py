"""
Async SQLAlchemy engine and session factory.

Usage (FastAPI dependency injection):
    from app.core.database import get_db

    @router.get("/items")
    async def list_items(db: AsyncSession = Depends(get_db)):
        ...

Usage (explicit context manager):
    from app.core.database import AsyncSessionLocal

    async with AsyncSessionLocal() as session:
        result = await session.execute(select(MyModel))
"""

from collections.abc import AsyncGenerator

import structlog
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import settings

logger = structlog.get_logger(__name__)

# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------

async_engine = create_async_engine(
    settings.database_url,
    # Connection pool
    pool_size=5,         # keep 5 connections open
    max_overflow=15,     # allow 15 extra → max 20 total connections
    pool_timeout=30,     # raise TimeoutError if no connection available within 30s
    pool_pre_ping=True,  # test connections before checkout (handles dropped connections)
    pool_recycle=3600,   # recycle connections older than 1 hour
    # Query timeouts
    connect_args={
        "command_timeout": 30,  # asyncpg client-side: kills connection after 30s
        "server_settings": {"statement_timeout": "30000"},  # Postgres server-side: kills query (ms)
    },
    # Disable echo in production; enable with LOG_LEVEL=DEBUG for query logging
    echo=settings.log_level.upper() == "DEBUG",
)

# ---------------------------------------------------------------------------
# Session factory
# ---------------------------------------------------------------------------

AsyncSessionLocal = async_sessionmaker(
    bind=async_engine,
    class_=AsyncSession,
    expire_on_commit=False,  # don't expire objects after commit (avoids lazy-load issues)
    autoflush=False,
    autocommit=False,
)


# ---------------------------------------------------------------------------
# FastAPI dependency
# ---------------------------------------------------------------------------


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Yield a database session for the duration of a request.

    Rolls back on any unhandled exception, then always closes the session.
    Use as a FastAPI dependency via Depends(get_db).
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
