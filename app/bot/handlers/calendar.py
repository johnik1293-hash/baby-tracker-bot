from __future__ import annotations

import logging
from aiogram import Router, F, types
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_session
from app.db.models import User, Baby
# Если у тебя есть модели Sleep / Feeding / CareLog — раскомментируй строки ниже.
# from app.db.models import Sleep, Feeding, CareLog

router = Router(name="calendar")
CALENDAR_ROWS = 15

log = logging.getLogger(__name__)


async def _get_or_create_user(session: AsyncSession, tg: types.User) -> User:
    """Находим или создаём пользователя по telegram_id."""
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


def _fmt(label: str, when, extra: str = "") -> str:
    ts = when.strftime("%d.%m %H:%M")
    return f"• {ts} — {label}" + (f" ({extra})" if extra else "")


@router.message(F.text.in_({"📅 Календарь", "Календарь"}))
async def calendar_last(message: types.Message):
    """Сводка последних событий: сон, кормления, уход."""
    # Для отладки убедимся, что задеплоилась нужная версия
    log.info("calendar.py handler loaded: version=async-for-session v2")

    lines: list[str] = []
    lines.append("📅 <b>Последние события</b>")

    # ВАЖНО: получаем AsyncSession через async for
    async for session in get_session():
        user = await _get_or_create_user(session, message.from_user)

        # Берём первого ребёнка пользователя (MVP). Если есть active_baby_id — подставь его.
        res_baby = await session.execute(
            select(Baby).where(Baby.user_id == user.id).order_by(Baby.id.asc()).limit(1)
        )
        baby = res_baby.scalar_one_or_none()

        # ---- Сон (раскомментируй, если модель Sleep существует) ----
        # try:
        #     q_sleep = select(Sleep).order_by(desc(Sleep.start_time)).limit(CALENDAR_ROWS)
        #     if baby:
        #         q_sleep = q_sleep.where(Sleep.baby_id == baby.id)
        #     res_sleep = await session.execute(q_sleep)
        #     sleeps = res_sleep.scalars().all()
        #     if sleeps:
        #         lines.append("\n<b>Сон:</b>")
        #         for s in sleeps:
        #             if s.end_time:
        #                 mins = int((s.end_time - s.start_time).total_seconds() // 60)
        #                 lines.append(_fmt("Сон завершён", s.end_time, extra=f"~{mins} мин"))
        #             else:
        #                 lines.append(_fmt("Сон начат", s.start_time))
        # except Exception as e:
        #     log.warning("Sleep block skipped: %s", e)

        # ---- Кормления (раскомментируй, если есть модель Feeding) ----
        # try:
        #     q_feed = select(Feeding).order_by(desc(Feeding.created_at)).limit(CALENDAR_ROWS)
        #     if baby:
        #         q_feed = q_feed.where(Feeding.baby_id == baby.id)
        #     res_feed = await session.execute(q_feed)
        #     feeds = res_feed.scalars().all()
        #     if feeds:
        #         lines.append("\n<b>Кормление:</b>")
        #         for f in feeds:
        #             extra = "; ".join(
        #                 x for x in [
        #                     f.type or "",
        #                     f"{getattr(f, 'amount_ml', None)} мл" if getattr(f, "amount_ml", None) else ""
        #                 ] if x
        #             )
        #             lines.append(_fmt("Кормление", f.created_at, extra=extra))
        # except Exception as e:
        #     log.warning("Feeding block skipped: %s", e)

        # ---- Уход (раскомментируй, если есть модель CareLog) ----
        # try:
        #     q_care = select(CareLog).order_by(desc(CareLog.created_at)).limit(CALENDAR_ROWS)
        #     if baby:
        #         q_care = q_care.where(CareLog.baby_id == baby.id)
        #     res_care = await session.execute(q_care)
        #     cares = res_care.scalars().all()
        #     if cares:
        #         lines.append("\n<b>Уход:</b>")
        #         for c in cares:
        #             lines.append(_fmt(c.action or "Действие", c.created_at, extra=c.note or ""))
        # except Exception as e:
        #     log.warning("CareLog block skipped: %s", e)

    await message.answer("\n".join(lines) if lines else "Пока записей нет.")
