from datetime import datetime, timezone
from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from app.config import get_settings


def utc_now() -> datetime:
    """Shared timestamp default for all ORM models. Single definition, no duplication."""
    return datetime.now(timezone.utc)

settings = get_settings()

engine = create_async_engine(
    settings.DATABASE_URL,
    echo=settings.DEBUG,
    pool_pre_ping=True,           # drops stale connections before use
    pool_size=settings.DB_POOL_SIZE,
    max_overflow=settings.DB_MAX_OVERFLOW,
    pool_recycle=settings.DB_POOL_RECYCLE,
    connect_args={
        "server_settings": {
            # Kills any query that runs longer than this — prevents a slow query
            # from holding a pool connection until the pool is exhausted.
            "statement_timeout": str(settings.DB_STATEMENT_TIMEOUT_MS),
            # Kills sessions that hold an open transaction but do nothing for 10 s.
            # Catches application bugs where a session is abandoned mid-transaction.
            "idle_in_transaction_session_timeout": "10000",
        }
    },
)

AsyncSessionFactory = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,  # objects remain usable after commit
)


class Base(DeclarativeBase):
    pass


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionFactory() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
