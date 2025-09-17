from __future__ import annotations

import asyncio
from datetime import datetime, timedelta

from aiogram import Bot
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_session
from app.db.models import Reminder, User

CHECK_INTERVAL_SECONDS = 30  # как часто проверять, сек

async def _process_due_reminders(bot: Bot):
    now = datetime.now()

    async for session in get_session():
        # Берём активные напоминания, срок которых настал
        q = await session.execute(
            select(Reminder).where(
                Reminder.is_active.is_(True),
                Reminder.next_run <= now
            )
        )
        reminders = q.scalars().all()

        for r in reminders:
            try:
                # Отправляем текст в чат
                await bot.send_message(chat_id=r.chat_id, text=f"⏰ Напоминание: {r.text}")

                if r.interval_minutes and r.interval_minutes > 0:
                    # Повторяющееся: переносим next_run
                    r.next_run = now + timedelta(minutes=r.interval_minutes)
                else:
                    # Одноразовое: деактивируем
                    r.is_active = False

            except Exception:
                # Если отправка не удалась — деактивируем, чтобы не зациклиться
                r.is_active = False

        if reminders:
            await session.commit()

async def reminders_worker(bot: Bot, stop_event: asyncio.Event):
    """Фоновая задача: раз в N секунд проверяет и рассылает напоминания."""
    while not stop_event.is_set():
        await _process_due_reminders(bot)
        try:
            await asyncio.wait_for(stop_event.wait(), timeout=CHECK_INTERVAL_SECONDS)
        except asyncio.TimeoutError:
            pass  # просто продолжаем цикл
