"""Async SQLAlchemy-сессии для FastAPI и игровых обработчиков."""

from functools import lru_cache

from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import NullPool

from src.persistence.settings import get_database_settings


@lru_cache
def get_database_engine() -> AsyncEngine:
    settings = get_database_settings()
    # TestClient и отдельные asyncio.run используют разные event loop.
    return create_async_engine(
        settings.database_url, pool_pre_ping=True, poolclass=NullPool
    )


@lru_cache
def get_session_factory() -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(get_database_engine(), expire_on_commit=False)
