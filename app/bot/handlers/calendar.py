# app/bot/handlers/calendar.py
from __future__ import annotations

from aiogram import Router, F
from aiogram.types import Message
from sqlalchemy import select, desc

from app.db.database import AsyncSessionLocal
from app.db.models import User  # импортируем только то, что точно есть

router = Router(name=__name__)


# Попытка импортировать таблицу событий, название может отличаться в вашем проекте.
# Поменяйте при необходимости на вашу реальную модель (например, Event, Log, Activity).
try:
    from app.db.models import CareLog as EventModel  # noqa: F401
except Exception:
    EventModel = None  # fallback — просто скажем, что событий нет


@router.message(F.text.in_({"📅 Календарь", "Календарь"}))
async def calendar_last(message: Message) -> None:
    """Показывает последние события пользователя (или семьи), если таблица событий есть."""
    if EventModel is None:
        await message.answer("Календарь пока недоступен: нет таблицы событий (CareLog).")
        return

    tg_id = message.from_user.id

    async with AsyncSessionLocal() as session:
        user = await session.scalar(select(User).where(User.telegram_id == tg_id))
        if not user:
            user = User(telegram_id=tg_id)
            session.add(user)
            await session.commit()
            await session.refresh(user)

        # Под ваши поля: попробуем 1) по family_id, если он есть, 2) по user_id, иначе ничего.
        q = None
        if hasattr(EventModel, "family_id") and getattr(user, "family_id", None):
            q = select(EventModel).where(
                EventModel.family_id == user.family_id
            ).order_by(desc(getattr(EventModel, "created_at", "id")))
        elif hasattr(EventModel, "user_id"):
            q = select(EventModel).where(
                EventModel.user_id == user.id
            ).order_by(desc(getattr(EventModel, "created_at", "id")))

        if q is None:
            await message.answer("Календарь: не удалось сопоставить поля модели событий (нужен family_id или user_id).")
            return

        result = await session.execute(q.limit(10))
        events = result.scalars().all()

    if not events:
        await message.answer("Событий пока нет. Добавьте запись, и она появится в календаре.")
        return

    lines = ["Последние события:"]
    for e in events:
        ts = getattr(e, "created_at", None) or getattr(e, "timestamp", None) or ""
        title = getattr(e, "title", None) or getattr(e, "event_type", None) or "Событие"
        detail = getattr(e, "note", None) or getattr(e, "description", None) or ""
        if detail:
            lines.append(f"• {title} — {detail} {f'({ts})' if ts else ''}")
        else:
            lines.append(f"• {title} {f'({ts})' if ts else ''}")

    await message.answer("\n".join(lines))
