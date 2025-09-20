# app/bot/handlers/children.py
from __future__ import annotations

from datetime import datetime, date
from typing import Optional

from aiogram import Router, F, types
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_session
from app.db.models import User, Baby, UserSettings

router = Router(name="children")

# -------- states --------
class AddBabyStates(StatesGroup):
    waiting_name = State()
    waiting_birthdate = State()

# -------- helpers --------
async def _get_or_create_user(session: AsyncSession, tg: types.User) -> User:
    q = await session.execute(select(User).where(User.telegram_id == tg.id))
    user = q.scalar_one_or_none()
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

def children_menu_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Добавить ребёнка", callback_data="child_add")],
        [InlineKeyboardButton(text="👶 Выбрать активного", callback_data="child_choose")],
    ])

def back_main_kb() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="Главное меню")]],
        resize_keyboard=True
    )

def babies_list_kb(pairs: list[tuple[int, str]]) -> InlineKeyboardMarkup:
    # pairs: [(id, "Имя (дата)"), ...]
    rows = [[InlineKeyboardButton(text=label, callback_data=f"child_set_{bid}")] for bid, label in pairs]
    rows.append([InlineKeyboardButton(text="↩️ Назад", callback_data="child_back")])
    return InlineKeyboardMarkup(inline_keyboard=rows)

def _fmt_date(d: Optional[date]) -> str:
    return d.strftime("%d.%m.%Y") if d else "не указана"

# -------- entry points --------
@router.message(F.text.in_({"👶 Профиль ребёнка", "Профиль ребёнка"}))
@router.message(Command("children"))
async def children_entry(message: types.Message, state: FSMContext):
    await state.clear()
    async for session in get_session():
        user = await _get_or_create_user(session, message.from_user)

        # активный ребёнок
        s = await session.execute(select(UserSettings).where(UserSettings.user_id == user.id))
        settings = s.scalar_one_or_none()

        active_label = "не выбран"
        if settings and settings.active_baby_id:
            b = await session.execute(select(Baby).where(Baby.id == settings.active_baby_id))
            bb = b.scalar_one_or_none()
            if bb:
                active_label = f"{bb.name} (др: {_fmt_date(bb.birth_date)})"

        # количество детей
        q = await session.execute(select(Baby).where(Baby.user_id == user.id))
        babies = q.scalars().all()

    text = (
        "👶 <b>Профиль ребёнка</b>\n\n"
        f"Активный: <b>{active_label}</b>\n"
        f"Всего детей: <b>{len(babies)}</b>\n\n"
        "Выберите действие:"
    )
    await message.answer(text, reply_markup=children_menu_kb())

# -------- add baby flow --------
@router.callback_query(F.data == "child_add")
async def child_add_start(cb: types.CallbackQuery, state: FSMContext):
    await cb.answer()
    await state.set_state(AddBabyStates.waiting_name)
    await cb.message.edit_text("Введите <b>имя</b> ребёнка:", reply_markup=None)

@router.message(AddBabyStates.waiting_name)
async def child_add_name(message: types.Message, state: FSMContext):
    name = (message.text or "").strip()
    if not name:
        await message.answer("Имя не должно быть пустым. Введите имя:")
        return
    await state.update_data(name=name)
    await state.set_state(AddBabyStates.waiting_birthdate)
    await message.answer(
        "Введите <b>дату рождения</b> в формате <code>дд.мм.гггг</code>\n"
        "Или отправьте «Пропустить».", reply_markup=back_main_kb()
    )

@router.message(AddBabyStates.waiting_birthdate)
async def child_add_birthdate(message: types.Message, state: FSMContext):
    raw = (message.text or "").strip()
    birth: Optional[date] = None

    if raw.lower() != "пропустить":
        try:
            birth = datetime.strptime(raw, "%d.%m.%Y").date()
        except ValueError:
            await message.answer("Неверный формат. Введите дату в виде <code>дд.мм.гггг</code> или отправьте «Пропустить».")
            return

    data = await state.get_data()
    name = data["name"]

    async for session in get_session():
        user = await _get_or_create_user(session, message.from_user)

        baby = Baby(user_id=user.id, name=name, birth_date=birth)
        session.add(baby)
        await session.flush()

        # если нет настроек или активный не выбран — назначим этого активным
        s = await session.execute(select(UserSettings).where(UserSettings.user_id == user.id))
        settings = s.scalar_one_or_none()
        if not settings:
            settings = UserSettings(user_id=user.id, active_baby_id=baby.id)
            session.add(settings)
        elif not settings.active_baby_id:
            settings.active_baby_id = baby.id

        await session.commit()

    await state.clear()
    await message.answer(
        f"✅ Ребёнок <b>{name}</b> добавлен (др: {_fmt_date(birth)}).\n"
        "Его назначили активным.",
        reply_markup=back_main_kb()
    )

# -------- choose active baby --------
@router.callback_query(F.data == "child_choose")
async def child_choose(cb: types.CallbackQuery):
    async for session in get_session():
        user = await _get_or_create_user(session, cb.from_user)
        q = await session.execute(select(Baby).where(Baby.user_id == user.id).order_by(Baby.id.asc()))
        babies = q.scalars().all()

    if not babies:
        await cb.answer()
        await cb.message.answer("Нет детей. Сначала добавьте ребёнка: «Профиль ребёнка» → «➕ Добавить ребёнка».")
        return

    pairs = []
    for b in babies:
        label = f"{b.name} (др: {_fmt_date(b.birth_date)})"
        pairs.append((b.id, label))

    await cb.answer()
    await cb.message.edit_text("Выберите активного ребёнка:", reply_markup=babies_list_kb(pairs))

@router.callback_query(F.data.startswith("child_set_"))
async def child_set_active(cb: types.CallbackQuery):
    baby_id = int(cb.data.split("_")[-1])
    async for session in get_session():
        user = await _get_or_create_user(session, cb.from_user)

        s = await session.execute(select(UserSettings).where(UserSettings.user_id == user.id))
        settings = s.scalar_one_or_none()
        if not settings:
            settings = UserSettings(user_id=user.id, active_baby_id=baby_id)
            session.add(settings)
        else:
            settings.active_baby_id = baby_id

        await session.commit()

        bq = await session.execute(select(Baby).where(Baby.id == baby_id))
        b = bq.scalar_one_or_none()

    name = b.name if b else "—"
    await cb.answer("Выбран активный ребёнок")
    await cb.message.edit_text(f"✅ Активный ребёнок: <b>{name}</b>", reply_markup=children_menu_kb())

@router.callback_query(F.data == "child_back")
async def child_back(cb: types.CallbackQuery):
    await cb.answer()
    await cb.message.edit_text("Профиль ребёнка. Выберите действие:", reply_markup=children_menu_kb())
