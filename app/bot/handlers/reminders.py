# app/bot/handlers/reminders.py
from __future__ import annotations

from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.utils.keyboard import InlineKeyboardBuilder

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import AsyncSessionLocal
from app.db.models import User  # предполагается, что модель уже есть

router = Router(name=__name__)

# ===== ВСПОМОГАТЕЛЬНОЕ =====

async def _ensure_user(tg_id: int) -> User:
    """Гарантируем, что пользователь есть в БД."""
    async with AsyncSessionLocal() as session:  # не используем get_session()
        u = await session.scalar(select(User).where(User.telegram_id == tg_id))
        if u:
            return u
        u = User(telegram_id=tg_id)
        session.add(u)
        await session.commit()
        await session.refresh(u)
        return u


def _settings_kb() -> InlineKeyboardBuilder:
    kb = InlineKeyboardBuilder()
    # Вернули прежние кнопки напоминаний — коллбеки пока заглушки.
    kb.button(text="⏰ Кормление", callback_data="remind:feed")
    kb.button(text="🧷 Подгузник", callback_data="remind:diaper")
    kb.button(text="😴 Сон", callback_data="remind:sleep")
    kb.button(text="🚶 Прогулка", callback_data="remind:walk")
    kb.button(text="🛁 Купание", callback_data="remind:bath")
    kb.button(text="⬅️ Назад", callback_data="settings:back")
    kb.adjust(2, 2, 1)
    return kb


# ===== ХЕНДЛЕРЫ =====

@router.message(F.text.in_({"⚙️ Настройки", "Настройки"}))
async def settings_menu(message: Message) -> None:
    """Открыть меню настроек."""
    await _ensure_user(message.from_user.id)
    kb = _settings_kb()
    await message.answer(
        "Настройки напоминаний:\n"
        "— Включите/выключите нужные категории.\n"
        "Пока без тонких интервалов; добавим позже.",
        reply_markup=kb.as_markup(),
    )


@router.callback_query(F.data == "settings:back")
async def cb_menu_back(callback: CallbackQuery) -> None:
    """Кнопка «Назад» из настроек."""
    await callback.message.edit_text("Главное меню. Выберите действие.")
    await callback.answer()


# Ниже простые заглушки на переключатели.
# Когда будете хранить флаги в БД — добавьте таблицу/поля у User и commit.

async def _toggle_stub(session: AsyncSession, user: User, field: str) -> bool:
    """Заглушка: всегда возвращает True (включено)."""
    # Пример для реальной логики:
    # current = getattr(user, field, False)
    # setattr(user, field, not current)
    # await session.commit()
    return True

async def _toggle_and_notify(callback: CallbackQuery, field: str, title: str) -> None:
    async with AsyncSessionLocal() as session:
        user = await _ensure_user(callback.from_user.id)
        enabled = await _toggle_stub(session, user, field)
    await callback.answer(f"{title}: {'включено' if enabled else 'выключено'}", show_alert=False)

@router.callback_query(F.data == "remind:feed")
async def remind_feed(callback: CallbackQuery) -> None:
    await _toggle_and_notify(callback, "remind_feed", "Кормление")

@router.callback_query(F.data == "remind:diaper")
async def remind_diaper(callback: CallbackQuery) -> None:
    await _toggle_and_notify(callback, "remind_diaper", "Подгузник")

@router.callback_query(F.data == "remind:sleep")
async def remind_sleep(callback: CallbackQuery) -> None:
    await _toggle_and_notify(callback, "remind_sleep", "Сон")

@router.callback_query(F.data == "remind:walk")
async def remind_walk(callback: CallbackQuery) -> None:
    await _toggle_and_notify(callback, "remind_walk", "Прогулка")

@router.callback_query(F.data == "remind:bath")
async def remind_bath(callback: CallbackQuery) -> None:
    await _toggle_and_notify(callback, "remind_bath", "Купание")
