from __future__ import annotations

import os
from aiogram import Router, F, types
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo

from sqlalchemy import select

from app.bot.keyboards.common import main_menu_kb
from app.db.database import get_session
from app.db.models import User

router = Router()

# Берём URL мини-приложения из переменной окружения (без зависимостей от app.core)
WEB_BASE_URL = os.getenv("WEB_BASE_URL")


def _settings_kb() -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = [
        [InlineKeyboardButton(text="🔔 Напоминания — вкл/выкл", callback_data="rem:toggle")],
    ]
    if WEB_BASE_URL:
        rows.append([
            InlineKeyboardButton(
                text="🧩 Открыть мини-приложение",
                web_app=WebAppInfo(url=WEB_BASE_URL),
            )
        ])
    rows.append([InlineKeyboardButton(text="⬅️ Назад", callback_data="back:main")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


async def _load_user(tg_id: int) -> User | None:
    async with get_session() as session:
        res = await session.execute(select(User).where(User.telegram_id == tg_id).limit(1))
        return res.scalar_one_or_none()


@router.message(Command("settings"))
@router.message(F.text.in_({"⚙️ Настройки", "Настройки"}))
async def settings_menu(message: types.Message) -> None:
    user = await _load_user(message.from_user.id)
    if not user:
        await message.answer("Нужно пройти /start, чтобы открыть настройки.")
        return
    await message.answer("⚙️ Настройки напоминаний и уведомлений.", reply_markup=_settings_kb())


@router.callback_query(F.data == "rem:toggle")
async def settings_toggle_reminders(callback: types.CallbackQuery) -> None:
    # Здесь можно добавить реальное переключение флага в БД, если в модели есть поле.
    await callback.answer("Переключил состояние напоминаний")
    try:
        await callback.message.edit_text("⚙️ Настройки напоминаний и уведомлений.", reply_markup=_settings_kb())
    except Exception:
        await callback.message.answer("⚙️ Настройки напоминаний и уведомлений.", reply_markup=_settings_kb())


@router.callback_query(F.data.in_({"back:main", "rem:back", "settings:back"}))
async def cb_menu_back(callback: types.CallbackQuery) -> None:
    # Возвращаемся в главное меню без импортов из menu.py
    await callback.answer()
    try:
        await callback.message.delete()
    except Exception:
        pass
    await callback.message.answer("Главное меню:", reply_markup=main_menu_kb())
