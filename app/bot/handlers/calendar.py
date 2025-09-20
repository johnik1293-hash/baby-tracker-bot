from __future__ import annotations

from aiogram import Router, F, types
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_session
from app.db.models import (
    User,
    Sleep,
    Feeding,
    CareLog,
    Baby,
)

router = Router(name="calendar")

# Сколько последних записей показывать в календаре
CALENDAR_ROWS = 15


async def _get_or_create_user(session: AsyncSession, tg: types.User) -> User:
    """Обеспечиваем наличие User в БД по telegram_id (MVP)."""
    res = await session.execute(select(User).where(User.telegram_id == tg.id))
    user = res.scalar_one_or_none()
    if not user:
        user = User(
            telegram_id=tg.id,
            username=tg.username,
            first_name=tg.first_name,
            last_name=tg.last_name,
        )
        session.add(user)
        await session.flush()
    return user


def _format_row(label: str, when, extra: str = "") -> str:
    """Красивое форматирование строки календаря."""
    ts = when.strftime("%d.%m %H:%M")
    if extra:
        return f"• {ts} — {label} ({extra})"
    return f"• {ts} — {label}"


@router.message(F.text.in_({"📅 Календарь", "Календарь"}))
async def calendar_last(message: types.Message):
    """
    Показываем сводку последних действий семьи/пользователя:
    - записи сна (начал/закончил)
    - кормления
    - записи из общего журнала заботы (CareLog)
    """
    # ВАЖНО: корректно получаем сессию
    async for session in get_session():
        user = await _get_or_create_user(session, message.from_user)

        # определяем текущего активного ребёнка пользователя (если у тебя есть такое поле)
        # или просто берём любого первого ребёнка как MVP
        res_baby = await session.execute(
            select(Baby).where(Baby.user_id == user.id).order_by(Baby.id.asc()).limit(1)
        )
        baby = res_baby.scalar_one_or_none()

        lines: list[str] = []
        lines.append("📅 <b>Последние события</b>")

        # 1) Сон (последние записи)
        q_sleep = (
            select(Sleep)
            .order_by(desc(Sleep.start_time))
            .limit(CALENDAR_ROWS)
        )
        if baby:
            q_sleep = q_sleep.where(Sleep.baby_id == baby.id)
        res_sleep = await session.execute(q_sleep)
        sleeps = res_sleep.scalars().all()
        if sleeps:
            lines.append("\n<b>Сон:</b>")
            for s in sleeps:
                if s.end_time:
                    lines.append(_format_row("Сон завершён", s.end_time, extra=f"длительность ~{int((s.end_time - s.start_time).total_seconds()//60)} мин"))
                else:
                    lines.append(_format_row("Сон начат", s.start_time))

        # 2) Кормления
        q_feed = (
            select(Feeding)
            .order_by(desc(Feeding.created_at))
            .limit(CALENDAR_ROWS)
        )
        if baby:
            q_feed = q_feed.where(Feeding.baby_id == baby.id)
        res_feed = await session.execute(q_feed)
        feeds = res_feed.scalars().all()
        if feeds:
            lines.append("\n<b>Кормление:</b>")
            for f in feeds:
                extra = []
                if f.type:
                    extra.append(f.type)
                if f.amount_ml:
                    extra.append(f"{f.amount_ml} мл")
                lines.append(_format_row("Кормление", f.created_at, extra="; ".join(extra)))

        # 3) Общие действия ухода — CareLog (купание, прогулка, укладывание и т.п.)
        q_care = (
            select(CareLog)
            .order_by(desc(CareLog.created_at))
            .limit(CALENDAR_ROWS)
        )
        if baby:
            q_care = q_care.where(CareLog.baby_id == baby.id)
        res_care = await session.execute(q_care)
        cares = res_care.scalars().all()
        if cares:
            lines.append("\n<b>Уход:</b>")
            for c in cares:
                lines.append(_format_row(c.action or "Действие", c.created_at, extra=c.note or ""))

    # выводим собранное
    await message.answer("\n".join(lines) if lines else "Пока записей нет.")
