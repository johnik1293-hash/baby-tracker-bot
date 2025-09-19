# app/bot/handlers/family.py
from __future__ import annotations
from datetime import datetime, timedelta
from uuid import uuid4

from aiogram import Router, types, F
from aiogram.filters import Command
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_session
from app.db.models import Family, FamilyMember, FamilyInvite, User
from app.services.carelog import get_user_family_id

router = Router(name="family")

@router.message(Command("family"))
async def family_menu(message: types.Message, session: AsyncSession = get_session()):
    user_id = message.from_user.id
    # найдём семью пользователя
    q = select(Family).join(FamilyMember).where(FamilyMember.user_id == select(User.id).where(User.telegram_id == user_id).scalar_subquery())
    res = await session.execute(q)
    family = res.scalar_one_or_none()

    if not family:
        kb = [
            [types.InlineKeyboardButton(text="➕ Создать семью", callback_data="family_create")],
            [types.InlineKeyboardButton(text="🔗 Ввести код приглашения", callback_data="family_join_prompt")],
        ]
        await message.answer("У тебя пока нет семьи.", reply_markup=types.InlineKeyboardMarkup(inline_keyboard=kb))
        return

    # есть семья — покажем
    kb = [
        [types.InlineKeyboardButton(text="👥 Участники", callback_data="family_members")],
        [types.InlineKeyboardButton(text="🔗 Пригласить (код)", callback_data="family_invite")],
        [types.InlineKeyboardButton(text="📅 Семейный календарь", callback_data="family_calendar")],
    ]
    await message.answer(f"Семья: <b>{family.title}</b>", reply_markup=types.InlineKeyboardMarkup(inline_keyboard=kb))

@router.callback_query(F.data == "family_create")
async def family_create(cb: types.CallbackQuery, session: AsyncSession = get_session()):
    tg_id = cb.from_user.id
    # найдём/создадим User
    u = await session.execute(select(User).where(User.telegram_id == tg_id))
    user = u.scalar_one_or_none()
    if not user:
        user = User(telegram_id=tg_id, username=cb.from_user.username, first_name=cb.from_user.first_name, last_name=cb.from_user.last_name)
        session.add(user)
        await session.flush()

    fam = Family(title="Наша семья")
    session.add(fam)
    await session.flush()

    fm = FamilyMember(family_id=fam.id, user_id=user.id, role="owner")
    session.add(fm)
    await session.commit()

    await cb.message.edit_text(f"Семья создана: <b>{fam.title}</b>.\nТеперь пригласи членов семьи: меню → /family → «Пригласить (код)»")
    await cb.answer()

@router.callback_query(F.data == "family_invite")
async def family_invite(cb: types.CallbackQuery, session: AsyncSession = get_session()):
    tg_id = cb.from_user.id
    # найдём user
    u = await session.execute(select(User).where(User.telegram_id == tg_id))
    user = u.scalar_one_or_none()
    if not user:
        await cb.answer("Ошибка: нет профиля пользователя", show_alert=True)
        return
    # найдём семью
    fam_id = await get_user_family_id(session, user.id)
    if not fam_id:
        await cb.answer("У тебя нет семьи", show_alert=True)
        return
    # создадим инвайт на 7 дней
    code = uuid4().hex[:8]
    inv = FamilyInvite(family_id=fam_id, code=code, expires_at=datetime.utcnow() + timedelta(days=7), is_active=True)
    session.add(inv)
    await session.commit()
    await cb.message.answer(f"Код приглашения: <code>{code}</code>\nДействителен 7 дней.\nНовый участник: /join {code}")
    await cb.answer()

@router.message(F.text.regexp(r"^/join\s+([A-Za-z0-9]+)$"))
async def family_join(message: types.Message, session: AsyncSession = get_session()):
    code = message.text.split(maxsplit=1)[1].strip()
    # инвайт
    q = select(FamilyInvite).where(FamilyInvite.code == code, FamilyInvite.is_active == True)  # noqa: E712
    res = await session.execute(q)
    inv = res.scalar_one_or_none()
    if not inv:
        await message.answer("Неверный или использованный код.")
        return
    if inv.expires_at and inv.expires_at < datetime.utcnow():
        await message.answer("Код истёк.")
        return

    tg_id = message.from_user.id
    u = await session.execute(select(User).where(User.telegram_id == tg_id))
    user = u.scalar_one_or_none()
    if not user:
        user = User(telegram_id=tg_id, username=message.from_user.username, first_name=message.from_user.first_name, last_name=message.from_user.last_name)
        session.add(user)
        await session.flush()

    # уже участник?
    exists = await session.execute(select(FamilyMember).where(FamilyMember.family_id == inv.family_id, FamilyMember.user_id == user.id))
    if exists.scalar_one_or_none():
        await message.answer("Ты уже в этой семье.")
        return

    session.add(FamilyMember(family_id=inv.family_id, user_id=user.id, role="parent"))
    await session.commit()
    await message.answer("Готово! Ты присоединился(ась) к семье. Открой /family.")
