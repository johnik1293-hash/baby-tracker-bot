from __future__ import annotations

from aiogram import Router, F, types
from aiogram.fsm.state import StatesGroup, State
from aiogram.fsm.context import FSMContext
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton
from datetime import datetime

from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_session
from app.db.models import User, Baby, UserSettings

router = Router(name="profile_multi")

# ---------- FSM ----------
class AddBabyStates(StatesGroup):
    waiting_name = State()
    waiting_birth_date = State()

class RenameBabyStates(StatesGroup):
    waiting_name = State()

class EditBirthStates(StatesGroup):
    waiting_birth_date = State()

# ---------- helpers ----------
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

async def _get_or_create_settings(session: AsyncSession, user_id: int) -> UserSettings:
    q = await session.execute(select(UserSettings).where(UserSettings.user_id == user_id))
    s = q.scalar_one_or_none()
    if not s:
        s = UserSettings(user_id=user_id, active_baby_id=None)
        session.add(s)
        await session.flush()
    return s

async def _list_babies(session: AsyncSession, user_id: int) -> list[Baby]:
    q = await session.execute(select(Baby).where(Baby.user_id == user_id).order_by(Baby.id.asc()))
    return q.scalars().all()

def _profile_menu_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Добавить ребёнка", callback_data="baby_add")],
        [InlineKeyboardButton(text="🔄 Сменить активного", callback_data="baby_switch")],
        [InlineKeyboardButton(text="✏️ Переименовать", callback_data="baby_rename")],
        [InlineKeyboardButton(text="📅 Изменить дату рождения", callback_data="baby_edit_date")],
        [InlineKeyboardButton(text="🗑 Удалить ребёнка", callback_data="baby_delete")],
    ])

def _babies_inline_list(babies: list[Baby], prefix: str, show_active_id: int | None) -> InlineKeyboardMarkup:
    rows = []
    for b in babies:
        tag = " ⭐" if show_active_id and b.id == show_active_id else ""
        rows.append([InlineKeyboardButton(text=f"{b.name}{tag}", callback_data=f"{prefix}_{b.id}")])
    return InlineKeyboardMarkup(inline_keyboard=rows or [[InlineKeyboardButton(text="(пока пусто)", callback_data="noop")]])

# ---------- entry ----------
@router.message(F.text == "Профиль ребёнка")
async def profile_start(message: types.Message, state: FSMContext):
    async for session in get_session():
        user = await _get_or_create_user(session, message.from_user)
        settings = await _get_or_create_settings(session, user.id)
        babies = await _list_babies(session, user.id)

    if not babies:
        await message.answer("👶 Похоже, у вас ещё нет профилей детей.\nНажмите «➕ Добавить ребёнка».", reply_markup=None)
        await message.answer("Управление профилями:", reply_markup=_profile_menu_kb())
        return

    active = next((b for b in babies if settings.active_baby_id == b.id), None)
    active_text = (f"<b>{active.name}</b>" if active else "не выбран")
    lines = [f"👶 Активный ребёнок: {active_text}", "", "Дети:"]
    for b in babies:
        bdate = b.birth_date.strftime("%d.%m.%Y") if b.birth_date else "—"
        star = " ⭐" if active and b.id == active.id else ""
        lines.append(f"• {b.name}{star} — {bdate}")
    await message.answer("\n".join(lines))
    await message.answer("Управление профилями:", reply_markup=_profile_menu_kb())

# ---------- add baby ----------
@router.callback_query(F.data == "baby_add")
async def baby_add_start(callback: types.CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.answer()
    await callback.message.answer("Введите имя ребёнка:")
    await state.set_state(AddBabyStates.waiting_name)

@router.message(AddBabyStates.waiting_name, F.text)
async def baby_add_name(message: types.Message, state: FSMContext):
    name = message.text.strip()
    if not name:
        await message.answer("Имя не должно быть пустым. Введите имя:")
        return
    await state.update_data(name=name)
    await message.answer("Введите дату рождения в формате ДД.ММ.ГГГГ (например, 15.03.2024):")
    await state.set_state(AddBabyStates.waiting_birth_date)

@router.message(AddBabyStates.waiting_birth_date, F.text)
async def baby_add_birth_date(message: types.Message, state: FSMContext):
    s = message.text.strip()
    try:
        dt = datetime.strptime(s, "%d.%m.%Y").date()
    except Exception:
        await message.answer("Неверный формат. Введите дату ДД.ММ.ГГГГ:")
        return

    data = await state.get_data()
    name = data["name"]

    async for session in get_session():
        user = await _get_or_create_user(session, message.from_user)
        baby = Baby(user_id=user.id, name=name, birth_date=dt)
        session.add(baby)
        await session.flush()
        # если активный не выбран — сделаем только что созданного активным
        settings = await _get_or_create_settings(session, user.id)
        if settings.active_baby_id is None:
            settings.active_baby_id = baby.id
        await session.commit()

    await state.clear()
    await message.answer(f"✅ Ребёнок «{name}» добавлен и выбран активным (если активного не было).")

# ---------- switch active ----------
@router.callback_query(F.data == "baby_switch")
async def baby_switch_list(callback: types.CallbackQuery):
    async for session in get_session():
        user = await _get_or_create_user(session, callback.from_user)
        settings = await _get_or_create_settings(session, user.id)
        babies = await _list_babies(session, user.id)

    await callback.answer()
    await callback.message.answer("Выберите активного ребёнка:",
                                  reply_markup=_babies_inline_list(babies, "baby_switch_choose", settings.active_baby_id))

@router.callback_query(F.data.startswith("baby_switch_choose_"))
async def baby_switch_apply(callback: types.CallbackQuery):
    baby_id = int(callback.data.split("_")[-1])
    async for session in get_session():
        user = await _get_or_create_user(session, callback.from_user)
        settings = await _get_or_create_settings(session, user.id)
        # проверим, что ребёнок принадлежит пользователю
        q = await session.execute(select(Baby).where(Baby.id == baby_id, Baby.user_id == user.id))
        baby = q.scalar_one_or_none()
        if not baby:
            await callback.answer()
            await callback.message.answer("Ребёнок не найден.")
            return
        settings.active_baby_id = baby.id
        await session.commit()

    await callback.answer()
    await callback.message.answer(f"⭐ Активный ребёнок переключён на: <b>{baby.name}</b>.")

# ---------- rename ----------
@router.callback_query(F.data == "baby_rename")
async def baby_rename_list(callback: types.CallbackQuery):
    async for session in get_session():
        user = await _get_or_create_user(session, callback.from_user)
        settings = await _get_or_create_settings(session, user.id)
        babies = await _list_babies(session, user.id)

    await callback.answer()
    await callback.message.answer("Выберите ребёнка для переименования:",
                                  reply_markup=_babies_inline_list(babies, "baby_rename_choose", settings.active_baby_id))

@router.callback_query(F.data.startswith("baby_rename_choose_"))
async def baby_rename_start(callback: types.CallbackQuery, state: FSMContext):
    baby_id = int(callback.data.split("_")[-1])
    await state.update_data(baby_id=baby_id)
    await callback.answer()
    await callback.message.answer("Введите новое имя:")
    await state.set_state(RenameBabyStates.waiting_name)

@router.message(RenameBabyStates.waiting_name, F.text)
async def baby_rename_save(message: types.Message, state: FSMContext):
    name = message.text.strip()
    if not name:
        await message.answer("Имя не должно быть пустым. Введите имя:")
        return
    data = await state.get_data()
    baby_id = int(data["baby_id"])

    async for session in get_session():
        user = await _get_or_create_user(session, message.from_user)
        q = await session.execute(select(Baby).where(Baby.id == baby_id, Baby.user_id == user.id))
        baby = q.scalar_one_or_none()
        if not baby:
            await message.answer("Ребёнок не найден.")
            return
        baby.name = name
        await session.commit()

    await state.clear()
    await message.answer(f"✅ Имя обновлено: <b>{name}</b>.")

# ---------- edit birth date ----------
@router.callback_query(F.data == "baby_edit_date")
async def baby_edit_date_list(callback: types.CallbackQuery):
    async for session in get_session():
        user = await _get_or_create_user(session, callback.from_user)
        settings = await _get_or_create_settings(session, user.id)
        babies = await _list_babies(session, user.id)

    await callback.answer()
    await callback.message.answer("Выберите ребёнка для изменения даты рождения:",
                                  reply_markup=_babies_inline_list(babies, "baby_edit_choose", settings.active_baby_id))

@router.callback_query(F.data.startswith("baby_edit_choose_"))
async def baby_edit_date_start(callback: types.CallbackQuery, state: FSMContext):
    baby_id = int(callback.data.split("_")[-1])
    await state.update_data(baby_id=baby_id)
    await callback.answer()
    await callback.message.answer("Введите дату рождения в формате ДД.ММ.ГГГГ:")
    await state.set_state(EditBirthStates.waiting_birth_date)

@router.message(EditBirthStates.waiting_birth_date, F.text)
async def baby_edit_date_save(message: types.Message, state: FSMContext):
    s = message.text.strip()
    try:
        dt = datetime.strptime(s, "%d.%m.%Y").date()
    except Exception:
        await message.answer("Неверный формат. Введите дату ДД.ММ.ГГГГ:")
        return
    data = await state.get_data()
    baby_id = int(data["baby_id"])

    async for session in get_session():
        user = await _get_or_create_user(session, message.from_user)
        q = await session.execute(select(Baby).where(Baby.id == baby_id, Baby.user_id == user.id))
        baby = q.scalar_one_or_none()
        if not baby:
            await message.answer("Ребёнок не найден.")
            return
        baby.birth_date = dt
        await session.commit()

    await state.clear()
    await message.answer(f"✅ Дата рождения обновлена: <b>{dt.strftime('%d.%m.%Y')}</b>.")

# ---------- delete ----------
@router.callback_query(F.data == "baby_delete")
async def baby_delete_list(callback: types.CallbackQuery):
    async for session in get_session():
        user = await _get_or_create_user(session, callback.from_user)
        settings = await _get_or_create_settings(session, user.id)
        babies = await _list_babies(session, user.id)

    await callback.answer()
    await callback.message.answer("Выберите ребёнка для удаления:",
                                  reply_markup=_babies_inline_list(babies, "baby_delete_choose", settings.active_baby_id))

@router.callback_query(F.data.startswith("baby_delete_choose_"))
async def baby_delete_apply(callback: types.CallbackQuery):
    baby_id = int(callback.data.split("_")[-1])
    async for session in get_session():
        user = await _get_or_create_user(session, callback.from_user)
        settings = await _get_or_create_settings(session, user.id)

        # найдём ребёнка
        q = await session.execute(select(Baby).where(Baby.id == baby_id, Baby.user_id == user.id))
        baby = q.scalar_one_or_none()
        if not baby:
            await callback.answer()
            await callback.message.answer("Ребёнок не найден.")
            return

        # если удаляем активного — сбрасываем активного
        if settings.active_baby_id == baby.id:
            settings.active_baby_id = None

        # удалим запись
        await session.execute(delete(Baby).where(Baby.id == baby.id))
        await session.commit()

    await callback.answer()
    await callback.message.answer("🗑 Профиль ребёнка удалён.")
