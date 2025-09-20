# app/bot/handlers/calendar.py
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from aiogram import Router, F
from aiogram.types import Message

from sqlalchemy import select
from app.db.database import AsyncSessionLocal
from app.db.models import User, Feeding, Sleep, CareLog  # подставьте ваши реальные модели

router = Router(name=__name__)

def _fmt_dt(dt: datetime) -> str:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).strftime("%d.%m %H:%M")

@router.message(F.text.in_({"📅 Календарь", "Календарь"}))
async def calendar_last(message: Message) -> None:
    """Показываем события за последние 24 часа по текущей семье/пользователю."""
    tg_id = message.from_user.id
    now = datetime.utcnow().replace(tzinfo=timezone.utc)
    since = now - timedelta(hours=24)

    async with AsyncSessionLocal() as session:
        user = await session.scalar(select(User).where(User.telegram_id == tg_id))
        if not user:
            user = User(telegram_id=tg_id)
            session.add(user)
            await session.commit()
            await session.refresh(user)

        # Если есть семьи — фильтруйте по family_id; иначе по user_id
        # Ниже примеры выборок; подстройте под ваши реальные поля:

        feedings = []
        sleeps = []
        cares = []

        try:
            feedings = (await session.execute(
                select(Feeding)
                .where(Feeding.user_id == user.id)
                .where(Feeding.created_at >= since)
                .order_by(Feeding.created_at.desc())
                .limit(10)
            )).scalars().all()
        except Exception:
            pass

        try:
            sleeps = (await session.execute(
                select(Sleep)
                .where(Sleep.user_id == user.id)
                .where(Sleep.start_at >= since)
                .order_by(Sleep.start_at.desc())
                .limit(10)
            )).scalars().all()
        except Exception:
            pass

        try:
            cares = (await session.execute(
                select(CareLog)
                .where(CareLog.user_id == user.id)
                .where(CareLog.created_at >= since)
                .order_by(CareLog.created_at.desc())
                .limit(10)
            )).scalars().all()
        except Exception:
            pass

    # Формируем ответ
    lines = ["Последние события (24ч):"]
    if feedings:
        lines.append("\n🍽 Кормления:")
        for f in feedings:
            lines.append(f"• {_fmt_dt(f.created_at)} — {getattr(f, 'amount_ml', '')} мл".strip())
    if sleeps:
        lines.append("\n😴 Сон:")
        for s in sleeps:
            end = getattr(s, "end_at", None)
            if end:
                lines.append(f"• {_fmt_dt(s.start_at)} → {_fmt_dt(end)}")
            else:
                lines.append(f"• {_fmt_dt(s.start_at)} → … (ещё спит)")
    if cares:
        lines.append("\n🧷 Уход:")
        for c in cares:
            typ = getattr(c, "type", "")
            lines.append(f"• {_fmt_dt(c.created_at)} — {typ}")

    if len(lines) == 1:
        lines.append("Пока нет записей за последние 24 часа.")

    await message.answer("\n".join(lines))
