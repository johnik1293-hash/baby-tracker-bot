# app/db/database.py
from __future__ import annotations

import os
import logging
from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import declarative_base

log = logging.getLogger(__name__)

# --- URL БД ---------------------------------------------------------------

DATABASE_URL = os.getenv("DATABASE_URL", "").strip()

# Render часто даёт postgres URL как postgresql://...
# Для async-движка нужно postgresql+asyncpg://
if DATABASE_URL and DATABASE_URL.startswith("postgresql://"):
    DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://", 1)

# Локальный fallback (если вдруг нет переменной окружения)
if not DATABASE_URL:
    DATABASE_URL = "sqlite+aiosqlite:///./app.db"
    log.warning("DATABASE_URL is not set; using local SQLite fallback: %s", DATABASE_URL)

# --- Engine & sessionmaker -----------------------------------------------

async_engine: AsyncEngine = create_async_engine(
    DATABASE_URL,
    echo=False,
    pool_pre_ping=True,
)

AsyncSessionLocal: async_sessionmaker[AsyncSession] = async_sessionmaker(
    bind=async_engine,
    expire_on_commit=False,
    class_=AsyncSession,
)

# Базовый класс моделей
Base = declarative_base()


# --- Сессия как ASYNC CONTEXT MANAGER ------------------------------------

@asynccontextmanager
async def get_session() -> AsyncSession:
    """
    Правильный async context manager:
        async with get_session() as session:
            ...
    """
    session: AsyncSession = AsyncSessionLocal()
    try:
        yield session
        # Коммит на совести вызывающего кода (там, где нужны записи)
    except Exception:
        # В случае ошибки откатываем транзакцию,
        # чтобы не оставлять сессию в грязном состоянии.
        try:
            await session.rollback()
        except Exception:
            pass
        raise
    finally:
        await session.close()


# --- Инициализация схемы --------------------------------------------------

async def init_db() -> None:
    """
    Создаёт таблицы по Base.metadata (idempotent).
    Вызовите на старте приложения.
    """
    # Локальный импорт, чтобы избежать циклических зависимостей:
    from app.db import models  # noqa: F401

    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    log.info("DB schema is ready.")
