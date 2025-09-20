from __future__ import annotations

from datetime import datetime
from typing import Optional

from aiogram import Router, F, types
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_session
from app.db.models import User, Baby, SleepRecord, UserSettings
from app.services.carelog import log_event

router = Router(name="sleep_db")

# --- ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ---

def sleep_inline_quality_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="Отлично 😴", callback_data="quality_good"),
            InlineKeyboardButton(text="Нормально 🙂", callback_data="quality_ok"),
            InlineKeyboardButton(text="Беспокойно 😕", callback_data="quality_bad"),
        ]
    ])

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

async def _get_active_baby(session: AsyncSession, user_id: int) -> Optional[Baby]:
    # сначала пробуем активного
    qs = await session.execute(select(UserSettings).where(UserSettings.user_id == user_id))
    settings = qs.scalar_one_or_none()
    if settings and settings.active_baby_id:
        qb = await session.execute(select(Baby).where(Baby.id == settings.active_baby_id, Baby.user_id == user_id))
        baby = qb.scalar_one_or_none()
        if baby:
            return baby
    # иначе — первый по списку
    qb = await session.execute(select(Baby).where(Baby.user_id == user_id).order_by(Baby.id.asc()).limit(1))
    return qb.scalar_one_or_none()

async def _get_open_sleep(session: AsyncSession, baby_id: int) -> Optional[SleepRecord]:
    q = await session.execute(
        select(SleepRecord)
        .where(SleepRecord.baby_id == baby_id, SleepRecord.sleep_end.is_(None))
        .order_by(SleepRecord.sleep_start.desc())
        .limit(1)
    )
    return q.scalar_one_or_none()

# --- ХЕНДЛЕРЫ ---

@router.message(F.text == "Начал спать")
async def sleep_start(message: types.Message):
    async for session in get_session():
        user = await _get_or_create_user(session, message.from_user)
        baby = await _get_active_baby(session, user.id)

        if not baby:
            await message.answer(
                "❗️ Сначала создайте профиль ребёнка: «Профиль ребёнка» → введите имя и дату рождения."
            )
            return

        # Если уже есть незакрытая запись сна — не создаём вторую
        open_rec = await _get_open_sleep(session, baby.id)
        if open_rec:
            await message.answer("У вас уже зафиксировано начало сна. Нажмите «Проснулся», когда ребёнок проснётся.")
            return

        rec = SleepRecord(baby_id=baby.id, sleep_start=datetime.now())
        session.add(rec)
        await session.commit()

        # Лог в семейный календарь
        await log_event(session, actor_user_id=user.id, event_type="sleep_start", details="старт сна", baby_id=baby.id)

    await message.answer("🛌 Засыпание зафиксировано. Когда проснётся — нажмите «Проснулся».")

@router.message(F.text == "Проснулся")
async def sleep_end(message: types.Message):
    async for session in get_session():
        user = await _get_or_create_user(session, message.from_user)
        baby = await _get_active_baby(session, user.id)

        if not baby:
            await message.answer(
                "❗️ Сначала создайте профиль ребёнка: «Профиль ребёнка» → введите имя и дату рождения."
            )
            return

        rec = await _get_open_sleep(session, baby.id)
        if not rec:
            await message.answer("❌ Нет записи о начале сна. Сначала нажмите «Начал спать».")
            return

        rec.sleep_end = datetime.now()
        rec.duration_minutes = int((rec.sleep_end - rec.sleep_start).total_seconds() // 60)
        await session.commit()

        minutes = rec.duration_minutes or 0
        # Лог в семейный календарь
        await log_event(session, actor_user_id=user.id, event_type="sleep_end", details=f"сон {minutes} мин", baby_id=baby.id)

        hours = minutes // 60
        mins = minutes % 60

    await message.answer(
        f"✅ Пробуждение!\nДлительность: {hours}ч {mins}м\n\nОцените качество сна:",
        reply_markup=sleep_inline_quality_kb()
    )

@router.callback_query(F.data.startswith("quality_"))
async def sleep_quality(callback: types.CallbackQuery):
    quality = callback.data.replace("quality_", "")  # good|ok|bad

    async for session in get_session():
        user = await _get_or_create_user(session, callback.from_user)
        baby = await _get_active_baby(session, user.id)
        if not baby:
            await callback.answer()
            await callback.message.answer("❗️ Сначала создайте профиль ребёнка в разделе «Профиль ребёнка».")
            return

        # Берём последнюю закрытую запись без качества
        q = await session.execute(
            select(SleepRecord)
            .where(SleepRecord.baby_id == baby.id, SleepRecord.sleep_end.is_not(None))
            .order_by(SleepRecord.sleep_end.desc())
            .limit(1)
        )
        rec = q.scalar_one_or_none()
        if not rec:
            await callback.answer()
            await callback.message.answer("❌ Нет завершённой записи сна для установки качества.")
            return

        rec.quality = quality
        await session.commit()

    mapping = {"good": "Отлично 😴", "ok": "Нормально 🙂", "bad": "Беспокойно 😕"}
    human = mapping.get(quality, quality)
    await callback.answer()
    await callback.message.answer(f"Качество сна: <b>{human}</b> сохранено.")
