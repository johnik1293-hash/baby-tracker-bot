from __future__ import annotations

import asyncio
from datetime import datetime, timedelta
from typing import List, Tuple, Any

from aiogram import Router, F, types
from sqlalchemy import select, desc

from app.db.database import get_session
from app.db.models import User  # точно есть

# Модели событий могут отличаться у вас по именам — пробуем безопасно импортировать
try:
    from app.db.models import Feeding  # fields: id, baby_id, time, amount, side?, created_at?
except Exception:
    Feeding = None  # type: ignore

try:
    from app.db.models import Sleep  # fields: id, baby_id, start_time, end_time, quality?, created_at?
except Exception:
    Sleep = None  # type: ignore

try:
    from app.db.models import DiaperChange  # fields: id, baby_id, time, type, created_at?
except Exception:
    DiaperChange = None  # type: ignore

try:
    from app.db.models import Bathing  # fields: id, baby_id, time, created_at?
except Exception:
    Bathing = None  # type: ignore

router = Router()


def _fmt_dt(dt: datetime) -> str:
    return dt.strftime("%d.%m %H:%M")


async def _load_user(tg_id: int) -> User | None:
    async with get_session() as session:
        res = await session.execute(select(User).where(User.telegram_id == tg_id).limit(1))
        return res.scalar_one_or_none()


async def _fetch_feedings(session, family_id: int, since: datetime, limit: int = 20) -> List[Tuple[datetime, str]]:
    if not Feeding:
        return []
    q = (
        select(Feeding)
        .where(Feeding.family_id == family_id, Feeding.time >= since)
        .order_by(desc(Feeding.time))
        .limit(limit)
    )
    res = await session.execute(q)
    items = res.scalars().all()
    out: List[Tuple[datetime, str]] = []
    for x in items:
        amount = getattr(x, "amount", None)
        msg = f"🍼 Кормление — {amount} мл" if amount else "🍼 Кормление"
        out.append((x.time, msg))
    return out


async def _fetch_sleep(session, family_id: int, since: datetime, limit: int = 20) -> List[Tuple[datetime, str]]:
    if not Sleep:
        return []
    q = (
        select(Sleep)
        .where(Sleep.family_id == family_id, Sleep.start_time >= since)
        .order_by(desc(Sleep.start_time))
        .limit(limit)
    )
    res = await session.execute(q)
    items = res.scalars().all()
    out: List[Tuple[datetime, str]] = []
    for x in items:
        start = getattr(x, "start_time", None)
        end = getattr(x, "end_time", None)
        dur_txt = ""
        if start and end and isinstance(start, datetime) and isinstance(end, datetime):
            mins = int((end - start).total_seconds() // 60)
            dur_txt = f" ~ {mins} мин"
        out.append((start or getattr(x, "created_at", datetime.utcnow()), f"😴 Сон{dur_txt}"))
    return out


async def _fetch_diapers(session, family_id: int, since: datetime, limit: int = 20) -> List[Tuple[datetime, str]]:
    if not DiaperChange:
        return []
    q = (
        select(DiaperChange)
        .where(DiaperChange.family_id == family_id, DiaperChange.time >= since)
        .order_by(desc(DiaperChange.time))
        .limit(limit)
    )
    res = await session.execute(q)
    items = res.scalars().all()
    out: List[Tuple[datetime, str]] = []
    for x in items:
        t = getattr(x, "type", None)
        kind = f" — {t}" if t else ""
        out.append((x.time, f"🧷 Подгузник{kind}"))
    return out


async def _fetch_bathing(session, family_id: int, since: datetime, limit: int = 20) -> List[Tuple[datetime, str]]:
    if not Bathing:
        return []
    q = (
        select(Bathing)
        .where(Bathing.family_id == family_id, Bathing.time >= since)
        .order_by(desc(Bathing.time))
        .limit(limit)
    )
    res = await session.execute(q)
    items = res.scalars().all()
    out: List[Tuple[datetime, str]] = []
    for x in items:
        out.append((x.time, "🛁 Купание"))
    return out


async def _collect_events(family_id: int) -> List[Tuple[datetime, str]]:
    since = datetime.utcnow() - timedelta(days=7)  # последние 7 дней
    async with get_session() as session:
        results = await asyncio.gather(
            _fetch_feedings(session, family_id, since),
            _fetch_sleep(session, family_id, since),
            _fetch_diapers(session, family_id, since),
            _fetch_bathing(session, family_id, since),
            return_exceptions=False,
        )
    events: List[Tuple[datetime, str]] = []
    for chunk in results:
        events.extend(chunk)
    # Сортировка по убыванию времени
    events.sort(key=lambda x: x[0], reverse=True)
    # ограничим до 20 последних
    return events[:20]


@router.message(F.text.in_({"📅 Календарь", "Календарь"}))
async def calendar_last(message: types.Message) -> None:
    user = await _load_user(message.from_user.id)
    if not user:
        await message.answer("Нужно пройти /start, чтобы открыть календарь.")
        return
    if not getattr(user, "family_id", None):
        await message.answer("Сначала создайте семью в меню «👨‍👩‍👧 Семья», чтобы видеть общий календарь.")
        return

    events = await _collect_events(user.family_id)
    if not events:
        await message.answer("Пока событий нет за последние 7 дней.")
        return

    lines = [f"{_fmt_dt(ts)} — {text}" for ts, text in events]
    await message.answer("Последние события:\n\n" + "\n".join(lines))
