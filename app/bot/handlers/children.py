# app/bot/handlers/children.py
from __future__ import annotations

from aiogram import Router, F
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery
from aiogram.utils.keyboard import InlineKeyboardBuilder

from sqlalchemy import select

from app.db.database import AsyncSessionLocal
from app.db.models import User, Baby  # если у вас модель называется Child — замените на Child

router = Router(name=__name__)


async def _ensure_user(tg_id: int) -> User:
    async with AsyncSessionLocal() as session:
        user = await session.scalar(select(User).where(User.telegram_id == tg_id))
        if user:
            return user
        user = User(telegram_id=tg_id)
        session.add(user)
        await session.commit()
        await session.refresh(user)
        return user


def _children_menu_kb(has_kids: bool) -> InlineKeyboardBuilder:
    kb = InlineKeyboardBuilder()
    kb.button(text="➕ Добавить ребёнка", callback_data="child:add")
    if has_kids:
        kb.button(text="✏️ Редактировать", callback_data="child:edit")
    kb.button(text="⬅️ Назад", callback_data="child:back")
    kb.adjust(1, 1, 1)
    return kb


@router.message(F.text.in_({"👶 Профиль ребёнка", "Профиль ребёнка"}))
async def children_entry(message: Message, state: FSMContext) -> None:
    user = await _ensure_user(message.from_user.id)

    # Загружаем детей пользователя (при другой схеме поменяйте условие)
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(Baby).where(Baby.user_id == user.id).order_by(Baby.id.desc())
        )
        babies = result.scalars().all()

    if babies:
        lines = ["Ваши дети:"]
        for b in babies:
            name = getattr(b, "name", "Без имени")
            dob = getattr(b, "birth_date", None)
            lines.append(f"• {name}" + (f" (рождён(а) {dob})" if dob else ""))
        text = "\n".join(lines)
    else:
        text = "Пока нет добавленных детей. Вы можете создать профиль ребёнка."

    kb = _children_menu_kb(has_kids=bool(babies))
    await message.answer(text, reply_markup=kb.as_markup())


@router.callback_query(F.data == "child:back")
async def child_back(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.message.edit_text("Главное меню. Выберите действие.")
    await callback.answer()


@router.callback_query(F.data == "child:add")
async def child_add(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    await callback.message.answer(
        "Добавление ребёнка пока в разработке. Напишите имя и дату рождения — добавим это в следующем обновлении."
    )


@router.callback_query(F.data == "child:edit")
async def child_edit(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    await callback.message.answer(
        "Редактирование профиля ребёнка пока в разработке. Скоро добавим выбор ребёнка и поля для изменения."
    )
