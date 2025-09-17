from __future__ import annotations

from aiogram import Router, F, types
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_session
from app.db.models import User, Reminder, Baby

router = Router(name="reminders")

# ---------- helpers ----------

async def _get_or_create_user(session: AsyncSession, tg: types.User) -> User:
    from sqlalchemy import select
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

# ---------- FSM ----------

class ReminderOnceStates(StatesGroup):
    waiting_text = State()
    waiting_minutes = State()

class ReminderRepeatStates(StatesGroup):
    waiting_text = State()
    waiting_hours = State()

# ▼ новое: редактирование
class ReminderEditTextStates(StatesGroup):
    waiting_text = State()   # ждём новый текст; в FSM храним rid

class ReminderEditIntervalStates(StatesGroup):
    waiting_minutes = State()  # ждём новые минуты (0 = одноразовое)


# ---------- Меню напоминаний ----------

@router.message(F.text == "⏱ Мои напоминания")
async def list_reminders(message: types.Message):
    async for session in get_session():
        from sqlalchemy import select
        q = await session.execute(
            select(Reminder).where(
                Reminder.chat_id == message.chat.id,
                Reminder.is_active.is_(True)
            ).order_by(Reminder.next_run.asc())
        )
        items = q.scalars().all()

    if not items:
        await message.answer("Пока нет активных напоминаний.")
        return

    for r in items:
        typ = "повтор" if r.interval_minutes else "одноразовое"
        when = r.next_run.strftime("%d.%m %H:%M")
        every = f" (каждые {r.interval_minutes} мин)" if r.interval_minutes else ""
        text = f"⏱ <b>#{r.id}</b> — {r.text}\nТип: {typ}\nКогда: {when}{every}"

        kb = types.InlineKeyboardMarkup(inline_keyboard=[
            [
                types.InlineKeyboardButton(text="🧹 Отключить", callback_data=f"rem_stop_{r.id}"),
                types.InlineKeyboardButton(text="🗑 Удалить", callback_data=f"rem_del_{r.id}"),
            ],
            [
                types.InlineKeyboardButton(text="✏️ Текст", callback_data=f"rem_edit_txt_{r.id}"),
                types.InlineKeyboardButton(text="⏱ Интервал", callback_data=f"rem_edit_int_{r.id}"),
            ],
            [
                types.InlineKeyboardButton(text="🔔 +15м", callback_data=f"rem_snooze_{r.id}_15"),
                types.InlineKeyboardButton(text="🔔 +30м", callback_data=f"rem_snooze_{r.id}_30"),
                types.InlineKeyboardButton(text="🔔 +60м", callback_data=f"rem_snooze_{r.id}_60"),
            ],
        ])
        await message.answer(text, reply_markup=kb)

@router.message(F.text == "Настройки")
async def settings_menu(message: types.Message):
    kb = types.ReplyKeyboardMarkup(
        keyboard=[
            [types.KeyboardButton(text="➕ Напоминание (через N минут)"),
             types.KeyboardButton(text="🔁 Напоминание (каждые N часов)")],
            [types.KeyboardButton(text="⏱ Мои напоминания"),
             types.KeyboardButton(text="🧹 Отключить все напоминания")],
            [types.KeyboardButton(text="Главное меню")],
        ],
        resize_keyboard=True,
    )
    await message.answer("⚙️ Настройки. Что сделать?", reply_markup=kb)


# ---------- Одноразовое: через N минут ----------

@router.message(F.text == "➕ Напоминание (через N минут)")
async def add_once_start(message: types.Message, state: FSMContext):
    await message.answer("Введите текст напоминания (например: «Покормить смесью»):")
    await state.set_state(ReminderOnceStates.waiting_text)

@router.message(ReminderOnceStates.waiting_text, F.text)
async def add_once_text(message: types.Message, state: FSMContext):
    text = message.text.strip()
    if not text:
        await message.answer("Текст пустой. Введите текст напоминания:")
        return
    await state.update_data(text=text)
    await message.answer("Через сколько минут напомнить? Введите число, например: 30")
    await state.set_state(ReminderOnceStates.waiting_minutes)

@router.message(ReminderOnceStates.waiting_minutes, F.text)
async def add_once_minutes(message: types.Message, state: FSMContext):
    s = message.text.strip()
    if not s.isdigit():
        await message.answer("Введите целое число минут, например: 45")
        return
    minutes = int(s)
    data = await state.get_data()
    text = data["text"]

    async for session in get_session():
        user = await _get_or_create_user(session, message.from_user)
        remind_at = datetime.now() + timedelta(minutes=minutes)
        session.add(Reminder(
            user_id=user.id,
            chat_id=message.chat.id,
            text=text,
            next_run=remind_at,
            interval_minutes=None,  # одноразовое
            is_active=True,
        ))
        await session.commit()

    await state.clear()
    await message.answer(f"✅ Готово! Напомню через {minutes} мин: «{text}»")

# ---------- Повторяющееся: каждые N часов ----------

@router.message(F.text == "🔁 Напоминание (каждые N часов)")
async def add_repeat_start(message: types.Message, state: FSMContext):
    await message.answer("Введите текст напоминания (например: «Дать воду»):")
    await state.set_state(ReminderRepeatStates.waiting_text)

@router.message(ReminderRepeatStates.waiting_text, F.text)
async def add_repeat_text(message: types.Message, state: FSMContext):
    text = message.text.strip()
    if not text:
        await message.answer("Текст пустой. Введите текст напоминания:")
        return
    await state.update_data(text=text)
    await message.answer("С какой периодичностью повторять? Введите число часов, например: 3")
    await state.set_state(ReminderRepeatStates.waiting_hours)

@router.message(ReminderRepeatStates.waiting_hours, F.text)
async def add_repeat_hours(message: types.Message, state: FSMContext):
    s = message.text.strip()
    if not s.isdigit():
        await message.answer("Введите целое число часов, например: 4")
        return
    hours = int(s)
    minutes = hours * 60
    data = await state.get_data()
    text = data["text"]

    async for session in get_session():
        user = await _get_or_create_user(session, message.from_user)
        first_time = datetime.now() + timedelta(minutes=minutes)
        session.add(Reminder(
            user_id=user.id,
            chat_id=message.chat.id,
            text=text,
            next_run=first_time,
            interval_minutes=minutes,  # повтор
            is_active=True,
        ))
        await session.commit()

    await state.clear()
    await message.answer(f"✅ Готово! Буду напоминать каждые {hours} ч: «{text}»")

# ---------- Просмотр/отключение ----------

@router.message(F.text == "⏱ Мои напоминания")
async def list_reminders(message: types.Message):
    async for session in get_session():
        from sqlalchemy import select
        q = await session.execute(
            select(Reminder).where(Reminder.chat_id == message.chat.id, Reminder.is_active.is_(True)).order_by(Reminder.next_run.asc())
        )
        items = q.scalars().all()

    if not items:
        await message.answer("Пока нет активных напоминаний.")
        return

    lines = ["⏱ Активные напоминания:"]
    for r in items:
        typ = "повтор" if r.interval_minutes else "одноразовое"
        when = r.next_run.strftime("%d.%m %H:%M")
        every = f" (каждые {r.interval_minutes} мин)" if r.interval_minutes else ""
        lines.append(f"• {r.id}. {r.text} — {typ}: {when}{every}")

    await message.answer("\n".join(lines))

@router.message(F.text == "🧹 Отключить все напоминания")
async def disable_all(message: types.Message):
    async for session in get_session():
        q = await session.execute(
            select(Reminder).where(Reminder.chat_id == message.chat.id, Reminder.is_active.is_(True))
        )
        items = q.scalars().all()
        for r in items:
            r.is_active = False
        if items:
            await session.commit()

    await message.answer("🧹 Все напоминания отключены.")
@router.callback_query(F.data.startswith("rem_stop_"))
async def stop_reminder(callback: types.CallbackQuery):
    rid = int(callback.data.split("_")[-1])
    changed = False
    async for session in get_session():
        from sqlalchemy import select
        q = await session.execute(
            select(Reminder).where(
                Reminder.id == rid,
                Reminder.chat_id == callback.message.chat.id,
                Reminder.is_active.is_(True)
            )
        )
        r = q.scalar_one_or_none()
        if r:
            r.is_active = False
            await session.commit()
            changed = True

    await callback.answer()
    await callback.message.edit_text(f"❎ Напоминание #{rid} отключено." if changed else f"ℹ️ Напоминание #{rid} не найдено/уже неактивно.")

@router.callback_query(F.data.startswith("rem_del_"))
async def delete_reminder(callback: types.CallbackQuery):
    rid = int(callback.data.split("_")[-1])
    removed = False
    async for session in get_session():
        from sqlalchemy import select
        q = await session.execute(
            select(Reminder).where(
                Reminder.id == rid,
                Reminder.chat_id == callback.message.chat.id
            )
        )
        r = q.scalar_one_or_none()
        if r:
            # мягкое удаление: просто is_active = False (чтобы воркер не трогал)
            r.is_active = False
            await session.commit()
            removed = True
    await callback.answer()
    await callback.message.edit_text(f"🗑 Напоминание #{rid} удалено." if removed else f"ℹ️ Напоминание #{rid} не найдено.")
@router.callback_query(F.data.startswith("rem_edit_txt_"))
async def edit_text_start(callback: types.CallbackQuery, state: FSMContext):
    rid = int(callback.data.split("_")[-1])
    await state.update_data(edit_rid=rid)
    await callback.answer()
    await callback.message.answer(f"✏️ Введите новый текст для напоминания #{rid}:")
    await state.set_state(ReminderEditTextStates.waiting_text)

@router.message(ReminderEditTextStates.waiting_text, F.text)
async def edit_text_save(message: types.Message, state: FSMContext):
    data = await state.get_data()
    rid = int(data.get("edit_rid"))
    new_text = message.text.strip()
    if not new_text:
        await message.answer("Текст пустой. Введите новый текст:")
        return

    updated = False
    async for session in get_session():
        from sqlalchemy import select
        q = await session.execute(
            select(Reminder).where(
                Reminder.id == rid,
                Reminder.chat_id == message.chat.id,
                Reminder.is_active.is_(True)
            )
        )
        r = q.scalar_one_or_none()
        if r:
            r.text = new_text
            await session.commit()
            updated = True

    await state.clear()
    await message.answer(f"✅ Текст напоминания #{rid} обновлён: «{new_text}»" if updated else f"ℹ️ Напоминание #{rid} не найдено/неактивно.")
@router.callback_query(F.data.startswith("rem_snooze_"))
async def snooze_reminder(callback: types.CallbackQuery):
    _, _, rid_str, mins_str = callback.data.split("_")
    rid = int(rid_str)
    add_min = int(mins_str)

    from datetime import datetime, timedelta
    changed = False
    async for session in get_session():
        from sqlalchemy import select
        q = await session.execute(
            select(Reminder).where(
                Reminder.id == rid,
                Reminder.chat_id == callback.message.chat.id,
                Reminder.is_active.is_(True)
            )
        )
        r = q.scalar_one_or_none()
        if r:
            r.next_run = datetime.now() + timedelta(minutes=add_min)
            await session.commit()
            changed = True

    await callback.answer()
    await callback.message.edit_text(
        f"🔔 Напоминание #{rid} отложено на {add_min} мин."
        if changed else f"ℹ️ Напоминание #{rid} не найдено/неактивно."
    )

