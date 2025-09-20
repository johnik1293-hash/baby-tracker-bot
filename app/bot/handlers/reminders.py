from __future__ import annotations

import os
from typing import Optional, Dict

from aiogram import Router, F, types
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo
from sqlalchemy import select

from app.bot.keyboards.common import main_menu_kb
from app.db.database import get_session
from app.db.models import User

router = Router()

WEB_BASE_URL = os.getenv("WEB_BASE_URL")

# Псевдо-хранилище переключателей на время: {user_id: {category: bool}}
# (Чтобы сразу вернуть интерфейс. Позже можно заменить на поля в БД.)
_memory_flags: Dict[int, Dict[str, bool]] = {}

CATEGORIES = [
    ("feed", "🍼 Кормление"),
    ("sleep", "😴 Сон"),
    ("diaper", "🧷 Подгузник"),
    ("bath", "🛁 Купание"),
    ("med", "💊 Лекарства"),
]


def _root_kb() -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(text=label, callback_data=f"settings:cat:{key}")]
        for key, label in CATEGORIES
    ]
    if WEB_BASE_URL:
        rows.append([
            InlineKeyboardButton(
                text="🧩 Открыть мини-приложение",
                web_app=WebAppInfo(url=WEB_BASE_URL)
            )
        ])
    rows.append([InlineKeyboardButton(text="⬅️ Назад", callback_data="back:main")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def _cat_kb(user_id: int, key: str) -> InlineKeyboardMarkup:
    enabled = _memory_flags.get(user_id, {}).get(key, True)
    toggle_text = "🔕 Выключить" if enabled else "🔔 Включить"
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=toggle_text, callback_data=f"settings:cat:{key}:toggle")],
        [InlineKeyboardButton(text="⏱ Настроить интервал (скоро)", callback_data="noop")],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="settings:open")]
    ])


async def _ensure_user(tg_id: int) -> Optional[User]:
    async with get_session() as session:
        res = await session.execute(select(User).where(User.telegram_id == tg_id).limit(1))
        return res.scalar_one_or_none()


@router.message(Command("settings"))
@router.message(F.text.in_({"⚙️ Настройки", "Настройки"}))
async def settings_menu(message: types.Message) -> None:
    user = await _ensure_user(message.from_user.id)
    if not user:
        await message.answer("Нужно пройти /start, чтобы открыть настройки.")
        return
    await message.answer("⚙️ Настройки напоминаний и уведомлений.\nВыберите категорию:", reply_markup=_root_kb())


@router.callback_query(F.data == "settings:open")
async def cb_settings_open(callback: types.CallbackQuery) -> None:
    await callback.answer()
    try:
        await callback.message.edit_text(
            "⚙️ Настройки напоминаний и уведомлений.\nВыберите категорию:",
            reply_markup=_root_kb()
        )
    except Exception:
        await callback.message.answer(
            "⚙️ Настройки напоминаний и уведомлений.\nВыберите категорию:",
            reply_markup=_root_kb()
        )


@router.callback_query(F.data.startswith("settings:cat:") & ~F.data.endswith(":toggle"))
async def cb_settings_open_category(callback: types.CallbackQuery) -> None:
    await callback.answer()
    parts = callback.data.split(":")
    key = parts[-1]
    label = next((lbl for k, lbl in CATEGORIES if k == key), "Категория")
    user_id = callback.from_user.id
    # инициализируем дефолт
    _memory_flags.setdefault(user_id, {}).setdefault(key, True)
    kb = _cat_kb(user_id, key)
    text = f"{label}\n\nЗдесь можно включать/выключать напоминания и задавать интервал."
    try:
        await callback.message.edit_text(text, reply_markup=kb)
    except Exception:
        await callback.message.answer(text, reply_markup=kb)


@router.callback_query(F.data.endswith(":toggle"))
async def cb_settings_toggle(callback: types.CallbackQuery) -> None:
    await callback.answer()
    parts = callback.data.split(":")
    # ожидаем settings:cat:<key>:toggle
    if len(parts) < 4:
        return
    key = parts[2]
    user_id = callback.from_user.id
    current = _memory_flags.setdefault(user_id, {}).get(key, True)
    _memory_flags[user_id][key] = not current
    label = next((lbl for k, lbl in CATEGORIES if k == key), "Категория")
    status = "включены" if _memory_flags[user_id][key] else "выключены"
    text = f"{label}\n\nНапоминания теперь {status}."
    try:
        await callback.message.edit_text(text, reply_markup=_cat_kb(user_id, key))
    except Exception:
        await callback.message.answer(text, reply_markup=_cat_kb(user_id, key))


@router.callback_query(F.data.in_({"back:main"}))
async def cb_menu_back(callback: types.CallbackQuery) -> None:
    await callback.answer()
    try:
        await callback.message.delete()
    except Exception:
        pass
    await callback.message.answer("Главное меню:", reply_markup=main_menu_kb())


@router.callback_query(F.data == "noop")
async def cb_noop(callback: types.CallbackQuery) -> None:
    await callback.answer("Скоро добавлю настройку интервалов 😉", show_alert=False)
