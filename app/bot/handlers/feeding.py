from __future__ import annotations

from datetime import datetime, date

from aiogram import Router, F, types
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_session
from app.db.models import User, Baby, FeedingRecord, UserSettings
from app.services.carelog import log_event

router = Router(name="feeding_db")

# ---------- Вспомогательные ----------

def amount_ml_kb(prefix: str) -> InlineKeyboardMarkup:
    # Кнопки объёмов для смеси/воды
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="30 мл",  callback_data=f"{prefix}_30"),
            InlineKeyboardButton(text="60 мл",  callback_data=f"{prefix}_60"),
            InlineKeyboardButton(text="90 мл",  callback_data=f"{prefix}_90"),
        ],
        [
            InlineKeyboardButton(text="120 мл", callback_data=f"{prefix}_120"),
            InlineKeyboardButton(text="150 мл", callback_data=f"{prefix}_150"),
            InlineKeyboardButton(text="180 мл", callback_data=f"{prefix}_180"),
        ],
    ])

def amount_g_kb(prefix: str) -> InlineKeyboardMarkup:
    # Кнопки граммов для прикорма
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="20 г",  callback_data=f"{prefix}_20"),
            InlineKeyboardButton(text="40 г",  callback_data=f"{prefix}_40"),
            InlineKeyboardButton(text="60 г",  callback_data=f"{prefix}_60"),
        ],
        [
            InlineKeyboardButton(text="80 г",  callback_data=f"{prefix}_80"),
            InlineKeyboardButton(text="100 г", callback_data=f"{prefix}_100"),
        ],
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

async def _get_active_baby(session: AsyncSession, user_id: int) -> Baby | None:
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

# ---------- Хендлеры сообщений ----------

@router.message(F.text == "Грудное молоко")
async def feeding_breast(message: types.Message):
    """Фиксируем событие грудного вскармливания (без объёма)."""
    async for session in get_session():
        user = await _get_or_create_user(session, message.from_user)
        baby = await _get_active_baby(session, user.id)
        if not baby:
            await message.answer("❗️ Сначала создайте профиль ребёнка в разделе «Профиль ребёнка».")
            return

        rec = FeedingRecord(baby_id=baby.id, feeding_type="breast")
        session.add(rec)
        await session.commit()

        # Лог в семейный календарь
        await log_event(session, actor_user_id=user.id, event_type="feeding", details="грудное молоко", baby_id=baby.id)

    await message.answer("🤱 Записано грудное вскармливание.")

@router.message(F.text == "Смесь")
async def feeding_formula(message: types.Message):
    kb = amount_ml_kb(prefix="formula_ml")
    await message.answer("🍼 Выберите объём смеси:", reply_markup=kb)

@router.message(F.text == "Вода")
async def feeding_water(message: types.Message):
    kb = amount_ml_kb(prefix="water_ml")
    await message.answer("💧 Выберите объём воды:", reply_markup=kb)

@router.message(F.text == "Прикорм")
async def feeding_solid(message: types.Message):
    kb = amount_g_kb(prefix="solid_g")
    await message.answer("🥣 Выберите количество прикорма (г):", reply_markup=kb)

@router.message(F.text == "Статистика кормления")
async def feeding_stats(message: types.Message):
    """Покажем последние 5 записей + итоги за сегодня."""
    async for session in get_session():
        user = await _get_or_create_user(session, message.from_user)
        baby = await _get_active_baby(session, user.id)
        if not baby:
            await message.answer("Нет данных. Сначала создайте профиль ребёнка и добавьте кормления.")
            return

        # последние 5
        q_last = await session.execute(
            select(FeedingRecord)
            .where(FeedingRecord.baby_id == baby.id)
            .order_by(FeedingRecord.fed_at.desc())
            .limit(5)
        )
        items = q_last.scalars().all()

        # агрегаты за сегодня (для простоты — по UTC-дате)
        today = date.today()
        day_start = datetime.combine(today, datetime.min.time())
        day_end = datetime.combine(today, datetime.max.time())

        q_sum_ml = await session.execute(
            select(func.coalesce(func.sum(FeedingRecord.amount_ml), 0))
            .where(
                FeedingRecord.baby_id == baby.id,
                FeedingRecord.fed_at >= day_start,
                FeedingRecord.fed_at <= day_end,
            )
        )
        total_ml = int(q_sum_ml.scalar_one() or 0)

        q_sum_g = await session.execute(
            select(func.coalesce(func.sum(FeedingRecord.amount_g), 0))
            .where(
                FeedingRecord.baby_id == baby.id,
                FeedingRecord.fed_at >= day_start,
                FeedingRecord.fed_at <= day_end,
            )
        )
        total_g = int(q_sum_g.scalar_one() or 0)

    if not items:
        await message.answer("Записей кормления ещё нет.")
        return

    type_map = {"breast": "Грудное молоко", "formula": "Смесь", "water": "Вода", "solid": "Прикорм"}

    lines = ["📝 Последние кормления:"]
    for r in items:
        t = r.fed_at.strftime("%d.%m %H:%M")
        tpe = type_map.get(r.feeding_type, r.feeding_type)
        vol = ""
        if r.amount_ml:
            vol = f" — {r.amount_ml} мл"
        if r.amount_g:
            vol = f" — {r.amount_g} г"
        if r.note:
            vol += f" ({r.note})"
        lines.append(f"• {t} | {tpe}{vol}")

    lines.append(f"\nИтого за сегодня: {total_ml} мл напитков + {total_g} г прикорма")
    await message.answer("\n".join(lines))

# ---------- Коллбэки выбора объёма ----------

@router.callback_query(F.data.startswith("formula_ml_"))
async def cb_formula_amount(callback: types.CallbackQuery):
    amount = int(callback.data.split("_")[-1])  # 30/60/...
    async for session in get_session():
        user = await _get_or_create_user(session, callback.from_user)
        baby = await _get_active_baby(session, user.id)
        if not baby:
            await callback.answer()
            await callback.message.answer("❗️ Сначала создайте профиль ребёнка в разделе «Профиль ребёнка».")
            return

        rec = FeedingRecord(baby_id=baby.id, feeding_type="formula", amount_ml=amount)
        session.add(rec)
        await session.commit()

        await log_event(session, actor_user_id=user.id, event_type="feeding", details=f"смесь {amount} мл", baby_id=baby.id)

    await callback.answer()
    await callback.message.answer(f"🍼 Смесь: {amount} мл — записано.")

@router.callback_query(F.data.startswith("water_ml_"))
async def cb_water_amount(callback: types.CallbackQuery):
    amount = int(callback.data.split("_")[-1])
    async for session in get_session():
        user = await _get_or_create_user(session, callback.from_user)
        baby = await _get_active_baby(session, user.id)
        if not baby:
            await callback.answer()
            await callback.message.answer("❗️ Сначала создайте профиль ребёнка в разделе «Профиль ребёнка».")
            return

        rec = FeedingRecord(baby_id=baby.id, feeding_type="water", amount_ml=amount)
        session.add(rec)
        await session.commit()

        await log_event(session, actor_user_id=user.id, event_type="feeding", details=f"вода {amount} мл", baby_id=baby.id)

    await callback.answer()
    await callback.message.answer(f"💧 Вода: {amount} мл — записано.")

@router.callback_query(F.data.startswith("solid_g_"))
async def cb_solid_amount(callback: types.CallbackQuery):
    amount = int(callback.data.split("_")[-1])
    async for session in get_session():
        user = await _get_or_create_user(session, callback.from_user)
        baby = await _get_active_baby(session, user.id)
        if not baby:
            await callback.answer()
            await callback.message.answer("❗️ Сначала создайте профиль ребёнка в разделе «Профиль ребёнка».")
            return

        rec = FeedingRecord(baby_id=baby.id, feeding_type="solid", amount_g=amount)
        session.add(rec)
        await session.commit()

        await log_event(session, actor_user_id=user.id, event_type="feeding", details=f"прикорм {amount} г", baby_id=baby.id)

    await callback.answer()
    await callback.message.answer(f"🥣 Прикорм: {amount} г — записано.")
