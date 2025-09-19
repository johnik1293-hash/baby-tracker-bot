# app/db/database.py
from __future__ import annotations

import os
from typing import Optional

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

# 1) Читаем DATABASE_URL из окружения
DATABASE_URL: str = os.getenv("DATABASE_URL", "").strip()

# Если переменная не задана — используем локальный SQLite (для Render тоже ок, но данные не сохранятся между деплоями)
if not DATABASE_URL:
    # Файл БД будет в папке проекта (можешь поменять путь)
    DATABASE_URL = "sqlite+aiosqlite:///./data.db"

# 2) Создаём async engine
#    Для SQLite дополнительных connect_args не нужно (aiosqlite их игнорирует)
async_engine: AsyncEngine = create_async_engine(
    DATABASE_URL,
    echo=False,
    pool_pre_ping=True,
)

# 3) Фабрика сессий
AsyncSessionLocal: async_sessionmaker[AsyncSession] = async_sessionmaker(
    bind=async_engine,
    expire_on_commit=False,
)
