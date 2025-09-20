from __future__ import annotations

from aiogram import Router, F, types
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from sqlalchemy import select

from app.db.database import get_session
from app.db.models import User  # если есть модель настроек RemindersSettings — подключи и её

router = Router(name="reminders")

# --- клавиатуры ---

def reminders_root_kb(enabled: bool) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(
                text=("🔔 Уведомления: ВКЛ" if enabled else "🔕 Уведомления: ВЫКЛ"),
                callback_data=("rem_toggle_off" if enabled else "rem_toggle_on")
            )
        ],
        [InlineKeyboardButton(text="⏱ Интервалы кормления", callback_data="rem_feeding")],
        [InlineKeyboardButton(text="😴 Интервалы сна", callback_data="rem_sleep")],
        [InlineKeyboardButton(text="⬅️ В меню", callback_data="menu_back")],
    ])

def back_to_settings_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="rem_back")]
    ])

# --- утилиты ---

async def _get_or_create_user(tg_user: types.User):
    async for session in get_session():
        res = await session.execute(select(User).where(User.telegram_id == tg_user.id))
        u = res.scalar_one_or_none()
        if not u:
            u = User(
                telegram_id=tg_user.id,
                username=tg_user.username,
                first_name=tg_user.first_name,
                last_name=tg_user.last_name
            )
            session.add(u)
            await session.commit()
        return u

# --- entry point кнопки/команды ---

@router.message(F.text.in_({"⚙️ Настройки", "Настройки"}))
async def open_settings(message: types.Message):
    # Здесь можно читать реальные настройки пользователя из таблицы, пока считаем включено=True
    enabled = True
    await message.answer(
        "⚙️ <b>Настройки напоминаний и уведомлений</b>\n\n"
        "Здесь можно включать/выключать напоминания и настроить интервалы.",
        reply_markup=reminders_root_kb(enabled),
        parse_mode="HTML"
    )

@router.callback_query(F.data == "rem_back")
async def cb_back(cb: CallbackQuery):
    await cb.answer()
    await open_settings(cb.message)

@router.callback_query(F.data == "menu_back")
async def cb_menu_back(cb: CallbackQuery):
    from app.bot.handlers.menu import main_menu  # локальный импорт чтобы избежать циклов
    await cb.answer()
    await main_menu(cb.message)

# --- переключатель напоминаний (MVP-хранилище в User.can_notify, если есть) ---

@router.callback_query(F.data.in_({"rem_toggle_on", "rem_toggle_off"}))
async def toggle_notifications(cb: CallbackQuery):
    turn_on = cb.data == "rem_toggle_on"
    async for session in get_session():
        res = await session.execute(select(User).where(User.telegram_id == cb.from_user.id))
        u = res.scalar_one_or_none()
        if not u:
            u = await _get_or_create_user(cb.from_user)

        # Если у модели User есть поле can_notify (Boolean) — используем его
        if hasattr(u, "can_notify"):
            u.can_notify = turn_on
            session.add(u)
            await session.commit()

    await cb.answer("Готово")
    await open_settings(cb.message)

# --- подстраницы (интервалы) ---

@router.callback_query(F.data == "rem_feeding")
async def rem_feeding(cb: CallbackQuery):
    await cb.answer()
    await cb.message.answer(
        "🍼 Интервалы кормления (MVP):\n"
        "— пока только отображение. В следующей версии добавим изменение.\n"
        "— дефолт: каждые 3 часа днём и 4 часа ночью.",
        reply_markup=back_to_settings_kb()
    )

@router.callback_query(F.data == "rem_sleep")
async def rem_sleep(cb: CallbackQuery):
    await cb.answer()
    await cb.message.answer(
        "😴 Интервалы сна (MVP):\n"
        "— пока только отображение. В следующей версии добавим изменение.\n"
        "— дефолт: бодрствование 60–90 минут (0–3 мес).",
        reply_markup=back_to_settings_kb()
    )
