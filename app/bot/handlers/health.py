from __future__ import annotations

from aiogram import Router, F, types
from aiogram.fsm.state import StatesGroup, State
from aiogram.fsm.context import FSMContext
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from datetime import datetime, date

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_session
from app.db.models import User, Baby, HealthRecord
from app.db.models import User, Baby, UserSettings  # + нужные модели раздела

router = Router(name="health_db")

# ---------- ВСПОМОГАТЕЛЬНЫЕ ----------

def temp_kb() -> InlineKeyboardMarkup:
    # Быстрый выбор температуры (можно расширять)
    row1 = [36.5, 36.8, 37.0]
    row2 = [37.5, 38.0, 38.5]
    row3 = [39.0, 39.5]
    def row(vals): return [InlineKeyboardButton(text=f"{v:.1f}°C", callback_data=f"temp_{v}") for v in vals]
    return InlineKeyboardMarkup(inline_keyboard=[row(row1), row(row2), row(row3)])

async def _get_or_create_user(session: AsyncSession, tg: types.User):
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

async def _get_primary_baby(session: AsyncSession, user_id: int):
    q = await session.execute(select(Baby).where(Baby.user_id == user_id).limit(1))
    return q.scalar_one_or_none()

# ---------- STATES ----------

class MedicineStates(StatesGroup):
    waiting_text = State()   # "Название, доза мг" или просто "Название"

class GrowthStates(StatesGroup):
    waiting_weight = State()  # граммы
    waiting_height = State()  # сантиметры

class VisitStates(StatesGroup):
    waiting_note = State()    # необязательная заметка

# ---------- TEMPERATURE ----------

@router.message(F.text == "Температура")
async def health_temperature(message: types.Message):
    kb = temp_kb()
    await message.answer("🌡 Выберите температуру (нажмите кнопку):", reply_markup=kb)

@router.callback_query(F.data.startswith("temp_"))
async def cb_temperature(callback: types.CallbackQuery):
    value = float(callback.data.split("_")[1])

    async for session in get_session():
        user = await _get_or_create_user(session, callback.from_user)
        baby = await _get_active_baby(session, user.id)
        if not baby:
            await callback.answer()
            await callback.message.answer("❗️ Сначала создайте профиль ребёнка в разделе «Профиль ребёнка».")
            return

        rec = HealthRecord(
            baby_id=baby.id,
            record_type="temperature",
            temperature_c=value
        )
        session.add(rec)
        await session.commit()

    await callback.answer()
    await callback.message.answer(f"🌡 Температура сохранена: <b>{value:.1f}°C</b>.")

# ---------- MEDICINE ----------

@router.message(F.text == "Лекарства")
async def health_medicine(message: types.Message, state: FSMContext):
    await message.answer(
        "💊 Введите лекарство (можно с дозой):\n"
        "Например: <code>Парацетамол 120</code> (мг)\n"
        "Или просто: <code>Ибупрофен</code>"
    )
    await state.set_state(MedicineStates.waiting_text)

@router.message(MedicineStates.waiting_text, F.text)
async def medicine_save(message: types.Message, state: FSMContext):
    text = message.text.strip()
    name, dose = text, None

    # Пытаемся вытащить число мг из конца строки
    parts = text.split()
    if parts and parts[-1].isdigit():
        dose = int(parts[-1])
        name = " ".join(parts[:-1]).strip() or "Лекарство"

    async for session in get_session():
        user = await _get_or_create_user(session, message.from_user)
        baby = await _get_active_baby(session, user.id)
        if not baby:
            await message.answer("❗️ Сначала создайте профиль ребёнка в разделе «Профиль ребёнка».")
            return

        rec = HealthRecord(
            baby_id=baby.id,
            record_type="medicine",
            medicine_name=name,
            dose_mg=dose
        )
        session.add(rec)
        await session.commit()

    await state.clear()
    suf = f", {dose} мг" if dose else ""
    await message.answer(f"💊 Записано: <b>{name}{suf}</b>.")

# ---------- DOCTOR VISIT ----------

@router.message(F.text == "Визит к врачу")
async def health_visit(message: types.Message, state: FSMContext):
    await message.answer("🏥 Визит зафиксирован текущим временем.\n"
                         "Можете добавить заметку (опционально). Напишите её текст или отправьте «Главное меню».")
    await state.set_state(VisitStates.waiting_note)

@router.message(VisitStates.waiting_note, F.text)
async def visit_save_note(message: types.Message, state: FSMContext):
    note = message.text.strip()
    async for session in get_session():
        user = await _get_or_create_user(session, message.from_user)
        baby = await _get_active_baby(session, user.id)
        if not baby:
            await message.answer("❗️ Сначала создайте профиль ребёнка.")
            return

        rec = HealthRecord(
            baby_id=baby.id,
            record_type="doctor_visit",
            visit_note=note
        )
        session.add(rec)
        await session.commit()

    await state.clear()
    await message.answer(f"🏥 Визит сохранён. Заметка: <b>{note}</b>")

# ---------- GROWTH / WEIGHT ----------

@router.message(F.text == "Рост/Вес")
async def growth_start(message: types.Message, state: FSMContext):
    await message.answer("⚖️ Введите вес в граммах (например: 6800):")
    await state.set_state(GrowthStates.waiting_weight)

@router.message(GrowthStates.waiting_weight, F.text)
async def growth_weight(message: types.Message, state: FSMContext):
    txt = message.text.strip()
    if not txt.isdigit():
        await message.answer("Введите число в граммах, например: 7200")
        return
    await state.update_data(weight_g=int(txt))
    await message.answer("📏 Теперь введите рост в сантиметрах (например: 65):")
    await state.set_state(GrowthStates.waiting_height)

@router.message(GrowthStates.waiting_height, F.text)
async def growth_height(message: types.Message, state: FSMContext):
    txt = message.text.strip()
    if not txt.isdigit():
        await message.answer("Введите число в сантиметрах, например: 67")
        return
    height_cm = int(txt)
    data = await state.get_data()
    weight_g = int(data.get("weight_g", 0))

    async for session in get_session():
        user = await _get_or_create_user(session, message.from_user)
        baby = await _get_active_baby(session, user.id)
        if not baby:
            await message.answer("❗️ Сначала создайте профиль ребёнка.")
            return

        rec = HealthRecord(
            baby_id=baby.id,
            record_type="growth",
            weight_g=weight_g,
            height_cm=height_cm
        )
        session.add(rec)
        await session.commit()

    await state.clear()
    await message.answer(f"✅ Рост/вес сохранены: <b>{weight_g} г</b>, <b>{height_cm} см</b>.")

# ---------- STATS ----------

@router.message(F.text == "Статистика здоровья")
async def health_stats(message: types.Message):
    async for session in get_session():
        user = await _get_or_create_user(session, message.from_user)
        baby = await _get_active_baby(session, user.id)
        if not baby:
            await message.answer("Нет данных. Сначала создайте профиль ребёнка.")
            return

        q = await session.execute(
            select(HealthRecord)
            .where(HealthRecord.baby_id == baby.id)
            .order_by(HealthRecord.created_at.desc())
            .limit(8)
        )
        items = q.scalars().all()

        # Средняя температура за сегодня
        today = date.today()
        q_avg_temp = await session.execute(
            select(func.avg(HealthRecord.temperature_c))
            .where(
                HealthRecord.baby_id == baby.id,
                HealthRecord.record_type == "temperature",
                HealthRecord.created_at >= datetime.combine(today, datetime.min.time()),
                HealthRecord.created_at <= datetime.combine(today, datetime.max.time()),
            )
        )
        avg_temp = q_avg_temp.scalar_one_or_none()

    if not items:
        await message.answer("Записей здоровья ещё нет.")
        return

    lines = ["🩺 Последние записи здоровья:"]
    for r in items:
        t = r.created_at.strftime("%d.%m %H:%M")
        if r.record_type == "temperature":
            lines.append(f"• {t} | Температура: {r.temperature_c:.1f}°C")
        elif r.record_type == "medicine":
            dose = f", {r.dose_mg} мг" if r.dose_mg else ""
            lines.append(f"• {t} | Лекарство: {r.medicine_name}{dose}")
        elif r.record_type == "doctor_visit":
            note = f" — {r.visit_note}" if r.visit_note else ""
            lines.append(f"• {t} | Визит к врачу{note}")
        elif r.record_type == "growth":
            w = f"{r.weight_g} г" if r.weight_g is not None else "—"
            h = f"{r.height_cm} см" if r.height_cm is not None else "—"
            lines.append(f"• {t} | Рост/вес: {w}, {h}")

    if avg_temp:
        lines.append(f"\nСредняя температура за сегодня: {avg_temp:.2f}°C")

    await message.answer("\n".join(lines))
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
