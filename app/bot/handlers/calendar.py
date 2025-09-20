from __future__ import annotations

from datetime import datetime, timedelta, timezone

from aiogram import Router, F, types
from sqlalchemy import select
from sqlalchemy.orm import joinedload

from app.db.database import get_session
from app.db.models import User, Baby

# Попытка импортировать универсальный журнал, если он у тебя есть
try:
    from app.db.models import CareLog
    HAS_CARELOG = True
except Exception:
    HAS_CARELOG = False

# Попытка резервных моделей
try:
    from app.db.models import Feeding
except Exception:
    Feeding = None

try:
    from app.db.models import Sleep
except Exception:
    Sleep = None

router = Router(name="calendar")

@router.message(F.text.in_({"📅 Календарь", "Календарь"}))
async def calendar_last(message: types.Message):
    tg_id = message.from_user.id
    now = datetime.now(timezone.utc)
    since = now - timedelta(days=1)

    async for session in get_session():
        # юзер
        u_res = await session.execute(select(User).where(User.telegram_id == tg_id))
        user = u_res.scalar_one_or_none()
        if not user:
            await message.answer("Пока нет данных. Сначала начните пользоваться ботом 😊")
            return

        lines = [f"📅 <b>Последние события за 24 часа</b>:"]
        events = []

        if HAS_CARELOG:
            # Берём журнал — за сутки
            q = (
                select(CareLog)
                .where(CareLog.at >= since)
                .options(joinedload(CareLog.baby))
                .order_by(CareLog.at.desc())
                .limit(25)
            )
            res = await session.execute(q)
            for row in res.scalars():
                baby_name = (row.baby.name if row.baby else "Без имени")
                when = row.at.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M")
                what = row.action  # например: feeding/sleep/bath/etc
                extra = []
                if getattr(row, "amount_ml", None):
                    extra.append(f"{row.amount_ml} мл")
                if getattr(row, "duration_min", None):
                    extra.append(f"{row.duration_min} мин")
                if getattr(row, "side", None):
                    extra.append(f"сторона: {row.side}")
                if getattr(row, "note", None):
                    extra.append(row.note)

                events.append((row.at, f"• {when} — {baby_name}: {what}" + (f" ({', '.join(extra)})" if extra else "")))
        else:
            # Резерв: склеиваем Feeding/Sleep если они существуют
            if Feeding is not None:
                qf = (
                    select(Feeding)
                    .where(Feeding.started_at >= since)
                    .options(joinedload(Feeding.baby))
                    .order_by(Feeding.started_at.desc())
                    .limit(25)
                )
                rf = await session.execute(qf)
                for f in rf.scalars():
                    baby_name = (f.baby.name if f.baby else "Без имени")
                    when = f.started_at.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M")
                    extra = []
                    if getattr(f, "amount_ml", None):
                        extra.append(f"{f.amount_ml} мл")
                    if getattr(f, "side", None):
                        extra.append(f"сторона: {f.side}")
                    events.append((f.started_at, f"• {when} — {baby_name}: кормление" + (f" ({', '.join(extra)})" if extra else "")))

            if Sleep is not None:
                qs = (
                    select(Sleep)
                    .where(Sleep.started_at >= since)
                    .options(joinedload(Sleep.baby))
                    .order_by(Sleep.started_at.desc())
                    .limit(25)
                )
                rs = await session.execute(qs)
                for s in rs.scalars():
                    baby_name = (s.baby.name if s.baby else "Без имени")
                    when = s.started_at.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M")
                    duration = ""
                    if getattr(s, "ended_at", None):
                        delta = (s.ended_at - s.started_at)
                        mins = max(1, int(delta.total_seconds() // 60))
                        duration = f" ({mins} мин)"
                    events.append((s.started_at, f"• {when} — {baby_name}: сон{duration}"))

        # вывод
        if not events:
            await message.answer("Пока нет событий за последние 24 часа.")
            return

        # сортировка по времени убыв.
        events.sort(key=lambda x: x[0], reverse=True)
        # только текст
        text = "\n".join([lines[0]] + [e[1] for e in events[:25]])
        await message.answer(text, parse_mode="HTML")
