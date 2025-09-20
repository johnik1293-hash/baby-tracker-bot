from __future__ import annotations

from aiogram import Router, F, types
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_session
from app.db.models import User, Family, FamilyMember

router = Router(name="family")

# ---------- helpers ----------

def family_menu_kb(has_family: bool) -> InlineKeyboardMarkup:
    if has_family:
        return InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="👥 Участники семьи", callback_data="fam_members")],
            [InlineKeyboardButton(text="🔗 Пригласить по коду", callback_data="fam_invite")],
            [InlineKeyboardButton(text="🚪 Покинуть семью", callback_data="fam_leave")],
        ])
    else:
        return InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="➕ Создать семью", callback_data="fam_create")],
            [InlineKeyboardButton(text="🔑 Ввести код приглашения", callback_data="fam_join")],
        ])


async def _get_or_create_user(session: AsyncSession, tg: types.User) -> User:
    res = await session.execute(select(User).where(User.telegram_id == tg.id))
    user = res.scalar_one_or_none()
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


async def _get_user_family(session: AsyncSession, user_id: int) -> Family | None:
    q = (
        select(Family)
        .join(FamilyMember, FamilyMember.family_id == Family.id)
        .where(FamilyMember.user_id == user_id)
        .limit(1)
    )
    res = await session.execute(q)
    return res.scalar_one_or_none()


# ---------- entry ----------

@router.message(F.text.in_({"👨‍👩‍👧 Семья", "Семья"}))
async def family_menu(message: types.Message):
    # ВАЖНО: берём сессию через async for, а не session = get_session()
    async for session in get_session():
        user = await _get_or_create_user(session, message.from_user)
        fam = await _get_user_family(session, user.id)

        if fam:
            # посчитаем участников
            mem_q = await session.execute(
                select(FamilyMember).where(FamilyMember.family_id == fam.id)
            )
            members = mem_q.scalars().all()
            text = (
                f"🏠 Ваша семья: <b>{fam.name or 'Без названия'}</b>\n"
                f"Участников: <b>{len(members)}</b>\n\n"
                "Выберите действие:"
            )
            kb = family_menu_kb(has_family=True)
        else:
            text = (
                "У вас пока нет семьи.\n\n"
                "Создайте семью или присоединитесь по коду приглашения:"
            )
            kb = family_menu_kb(has_family=False)

    await message.answer(text, reply_markup=kb)


# ---------- callbacks ----------

@router.callback_query(F.data == "fam_create")
async def fam_create(cb: types.CallbackQuery):
    async for session in get_session():
        user = await _get_or_create_user(session, cb.from_user)
        # если уже есть семья — просто обновим меню
        fam = await _get_user_family(session, user.id)
        if fam:
            await cb.answer("Семья уже создана")
            await family_menu(cb.message)
            return

        fam = Family(name=f"Семья {user.first_name or user.username or user.telegram_id}")
        session.add(fam)
        await session.flush()

        session.add(FamilyMember(family_id=fam.id, user_id=user.id, role="owner"))
        await session.commit()

    await cb.answer("Семья создана")
    await family_menu(cb.message)


@router.callback_query(F.data == "fam_members")
async def fam_members(cb: types.CallbackQuery):
    async for session in get_session():
        user = await _get_or_create_user(session, cb.from_user)
        fam = await _get_user_family(session, user.id)
        if not fam:
            await cb.answer()
            await cb.message.answer("Сначала создайте семью или вступите в существующую.")
            return

        mem_q = await session.execute(
            select(FamilyMember, User)
            .join(User, User.id == FamilyMember.user_id)
            .where(FamilyMember.family_id == fam.id)
            .order_by(FamilyMember.id.asc())
        )
        rows = mem_q.all()

    lines = ["👥 <b>Участники семьи</b>:"]
    for m, u in rows:
        who = u.first_name or u.username or str(u.telegram_id)
        role = m.role or "member"
        lines.append(f"• {who} — {role}")

    await cb.answer()
    await cb.message.answer("\n".join(lines))


@router.callback_query(F.data == "fam_invite")
async def fam_invite(cb: types.CallbackQuery):
    async for session in get_session():
        user = await _get_or_create_user(session, cb.from_user)
        fam = await _get_user_family(session, user.id)
        if not fam:
            await cb.answer()
            await cb.message.answer("Сначала создайте семью.")
            return

        # простой пригласительный код = id семьи (для MVP)
        code = str(fam.id)

    await cb.answer()
    await cb.message.answer(
        "🔗 Приглашение в семью:\n"
        f"Код: <code>{code}</code>\n\n"
        "Другой участник должен выбрать «Семья» → «Ввести код приглашения» и отправить этот код."
    )


@router.callback_query(F.data == "fam_join")
async def fam_join_prompt(cb: types.CallbackQuery):
    await cb.answer()
    await cb.message.answer(
        "Отправьте сообщением <b>код приглашения</b> (число). "
        "Я добавлю вас в соответствующую семью."
    )


@router.message(F.text.regexp(r"^\d{1,12}$"))
async def fam_join_apply(message: types.Message):
    code = int(message.text.strip())
    async for session in get_session():
        user = await _get_or_create_user(session, message.from_user)

        # есть ли такая семья?
        res = await session.execute(select(Family).where(Family.id == code))
        fam = res.scalar_one_or_none()
        if not fam:
            await message.answer("❌ Семья с таким кодом не найдена.")
            return

        # уже участник?
        res = await session.execute(
            select(FamilyMember).where(
                FamilyMember.family_id == fam.id,
                FamilyMember.user_id == user.id,
            )
        )
        exists = res.scalar_one_or_none()
        if exists:
            await message.answer("Вы уже участник этой семьи.")
            return

        session.add(FamilyMember(family_id=fam.id, user_id=user.id, role="member"))
        await session.commit()

    await message.answer(f"✅ Вы присоединились к семье: <b>{fam.name or fam.id}</b>")
    # покажем меню семьи
    await family_menu(message)


@router.callback_query(F.data == "fam_leave")
async def fam_leave(cb: types.CallbackQuery):
    async for session in get_session():
        user = await _get_or_create_user(session, cb.from_user)
        fam = await _get_user_family(session, user.id)
        if not fam:
            await cb.answer()
            await cb.message.answer("Вы не состоите в семье.")
            return

        # удаляем членство
        res = await session.execute(
            select(FamilyMember)
            .where(
                FamilyMember.family_id == fam.id,
                FamilyMember.user_id == user.id,
            )
        )
        m = res.scalar_one_or_none()
        if m:
            await session.delete(m)
            await session.commit()

    await cb.answer("Вы вышли из семьи")
    await family_menu(cb.message)
