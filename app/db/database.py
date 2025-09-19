# app/db/database.py
from __future__ import annotations

import os
from typing import AsyncIterator

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.db.models import Base


def _normalize_db_url(url: str) -> str:
    """
    Приводим URL Postgres к async-драйверу:
      postgres://...      -> postgresql+asyncpg://...
      postgresql://...    -> postgresql+asyncpg://...
    SQLite оставляем как есть.
    """
    if not url:
        return ""

    low = url.lower()
    if low.startswith("postgres://"):
        return "postgresql+asyncpg://" + url.split("://", 1)[1]
    if low.startswith("postgresql://") and "+asyncpg" not in low:
        return "postgresql+asyncpg://" + url.split("://", 1)[1]
    return url


# 1) Читаем DATABASE_URL
DATABASE_URL: str = os.getenv("DATABASE_URL", "").strip()

# Если не задан — используем локальный SQLite (файл рядом с проектом)
if not DATABASE_URL:
    DATABASE_URL = "sqlite+aiosqlite:///./baby_tracker.db"

# Принудительно переводим Postgres в asyncpg
DATABASE_URL = _normalize_db_url(DATABASE_URL)

# 2) Создаём async engine
async_engine: AsyncEngine = create_async_engine(
    DATABASE_URL,
    echo=False,
    pool_pre_ping=True,
)

# 3) Фабрика асинхронных сессий
AsyncSessionLocal: async_sessionmaker[AsyncSession] = async_sessionmaker(
    bind=async_engine,
    expire_on_commit=False,
)


# 4) DI-зависимость/утилита для FastAPI/хендлеров
async def get_session() -> AsyncIterator[AsyncSession]:
    async with AsyncSessionLocal() as session:
        yield session


# 5) Инициализация схемы БД (создание таблиц)
async def init_db() -> None:
    """Создать все таблицы по моделям (idempotent)."""
    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
