from __future__ import annotations

import json
from datetime import datetime

from aiogram import Router, F, types
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_session
from app.db.models import User, Baby, UserSettings, SleepRecord, FeedingRecord

router = Router(name="webapp")


# --- helpers ---

async def _get_or_create_user(session: AsyncSession, tg: types.User) -> User:
    q = await session.execute(select(User).where(User.telegram_id == tg.id))
    user = q.scalar_one_or_none()
    if not user:
        user = User(
            telegram_id=tg.id,
            username=tg.username,
            first_name=tg.first_name,
            last_name=tg.last_name
        )
        session.add(user)
        await session.flush()
    return user

async def _get_active_baby(session: AsyncSession, user_id: int) -> Baby | None:
    qs = await session.execute(select(UserSettings).where(UserSettings.user_id == user_id))
    settings = qs.scalar_one_or_none()
    if settings and settings.active_baby_id:
        qb = await session.execute(select(Baby).where(Baby.id == settings.active_baby_id, Baby.user_id == user_id))
        b = qb.scalar_one_or_none()
        if b: return b
    qb = await session.execute(select(Baby).where(Baby.user_id == user_id).order_by(Baby.id.asc()).limit(1))
    return qb.scalar_one_or_none()

async def _get_open_sleep(session: AsyncSession, baby_id: int) -> SleepRecord | None:
    q = await session.execute(
        select(SleepRecord)
        .where(SleepRecord.baby_id == baby_id, SleepRecord.sleep_end.is_(None))
        .order_by(SleepRecord.sleep_start.desc())
        .limit(1)
    )
    return q.scalar_one_or_none()


# --- handler ---

@router.message(F.web_app_data)
async def handle_webapp_data(message: types.Message):
    """Получаем JSON из Telegram.WebApp.sendData(...)"""
    try:
        payload = json.loads(message.web_app_data.data)
    except Exception:
        await message.answer("⚠️ Не удалось разобрать данные от WebApp.")
        return

    async for session in get_session():
        user = await _get_or_create_user(session, message.from_user)
        baby = await _get_active_baby(session, user.id)

        if not baby:
            await message.answer("❗️ Сначала создайте профиль ребёнка в разделе «Профиль ребёнка».")
            return

        t = payload.get("type")

        # Тестовый пинг
        if t == "ping":
            msg = payload.get("message", "нет текста")
            await message.answer(f"✅ Получено из WebApp: {msg}")
            return

        # Сон: начало
        if t == "sleep_start":
            open_rec = await _get_open_sleep(session, baby.id)
            if open_rec:
                await message.answer("Уже есть незавершённая запись сна. Нажмите «Проснулся» в боте или в WebApp.")
                return
            rec = SleepRecord(baby_id=baby.id, sleep_start=datetime.now())
            session.add(rec)
            await session.commit()
            await message.answer("🛌 Сон: старт записан (из WebApp).")
            return

        # Сон: конец
        if t == "sleep_end":
            rec = await _get_open_sleep(session, baby.id)
            if not rec:
                await message.answer("Нет незавершённой записи сна. Сначала начните сон.")
                return
            rec.sleep_end = datetime.now()
            rec.duration_minutes = int((rec.sleep_end - rec.sleep_start).total_seconds() // 60)
            await session.commit()
            await message.answer(f"✅ Сон завершён: {rec.duration_minutes} мин (из WebApp).")
            return

        # Кормление
        if t == "feeding":
            feeding_type = payload.get("feeding_type")
            amount_ml = payload.get("amount_ml")
            amount_g = payload.get("amount_g")

            if feeding_type not in {"breast", "formula", "water", "solid"}:
                await message.answer("⚠️ Неверный тип кормления.")
                return

            rec = FeedingRecord(
                baby_id=baby.id,
                feeding_type=feeding_type,
                amount_ml=amount_ml,
                amount_g=amount_g
            )
            session.add(rec)
            await session.commit()

            human = {
                "breast": "Грудное молоко",
                "formula": "Смесь",
                "water": "Вода",
                "solid": "Прикорм"
            }[feeding_type]
            tail = f" — {amount_ml} мл" if amount_ml else (f" — {amount_g} г" if amount_g else "")
            await message.answer(f"🍽 {human}{tail} (из WebApp) — записано.")
            return

    # Если тип не распознали
    await message.answer("ℹ️ Данные от WebApp получены, но не распознаны.")
