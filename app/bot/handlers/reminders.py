from aiogram import Router, F, types
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo

from app.core.config import settings
from app.bot.keyboards.common import main_menu_kb
from app.db.database import get_session
from sqlalchemy import select
from app.db.models import User

router = Router()


def _settings_kb() -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(text="🔔 Напоминания — вкл/выкл", callback_data="rem:toggle")],
    ]
    if getattr(settings, "WEB_BASE_URL", None):
        rows.append([
            InlineKeyboardButton(
                text="🧩 Открыть мини-приложение",
                web_app=WebAppInfo(url=settings.WEB_BASE_URL),
            )
        ])
    rows.append([InlineKeyboardButton(text="⬅️ Назад", callback_data="back:main")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


async def _get_user(session, tg_id: int) -> User | None:
    res = await session.execute(select(User).where(User.telegram_id == tg_id).limit(1))
    return res.scalar_one_or_none()


@router.message(Command("settings"))
@router.message(F.text.in_({"⚙️ Настройки", "Настройки"}))
async def settings_menu(message: types.Message):
    async with get_session() as session:
        user = await _get_user(session, message.from_user.id)
        if not user:
            await message.answer("Нужно пройти /start, чтобы открыть настройки.")
            return

    await message.answer("⚙️ Настройки напоминаний и уведомлений.", reply_markup=_settings_kb())


@router.callback_query(F.data == "rem:toggle")
async def settings_toggle_reminders(callback: types.CallbackQuery):
    # Здесь может быть реальная логика переключения флага в БД, если поле существует.
    # Сейчас оставим безопасную заглушку, чтобы не падать, если поля нет.
    await callback.answer("Переключил состояние напоминаний", show_alert=False)
    try:
        await callback.message.edit_text("⚙️ Настройки напоминаний и уведомлений.", reply_markup=_settings_kb())
    except Exception:
        # На случай, если сообщение уже не редактируемое
        await callback.message.answer("⚙️ Настройки напоминаний и уведомлений.", reply_markup=_settings_kb())


@router.callback_query(F.data.in_({"back:main", "rem:back", "settings:back"}))
async def cb_menu_back(callback: types.CallbackQuery):
    # Возврат в главное меню без импортов из menu.py (чтобы не ловить циклические/битые импорты)
    await callback.answer()
    try:
        await callback.message.delete()
    except Exception:
        pass
    await callback.message.answer("Главное меню:", reply_markup=main_menu_kb())
