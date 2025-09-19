# app/bot/handlers/calendar.py
from __future__ import annotations
from datetime import datetime, timedelta
from aiogram import Router, types
from aiogram.filters import Command
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_session
from app.db.models import CareEvent, User, FamilyMember, Baby

router = Router(name="calendar")

@router.message(Command("calendar"))
async def calendar_last(message: types.Message, session: AsyncSession = get_session()):
    tg_id = message.from_user.id
    u = await session.execute(select(User).where(User.telegram_id == tg_id))
    user = u.scalar_one_or_none()
    if not user:
        await message.answer("Сначала нажми /start")
        return

    # найдём семью
    fm = await session.execute(select(FamilyMember.family_id).where(FamilyMember.user_id == user.id))
    row = fm.first()
    if not row:
        await message.answer("Семья не настроена. Открой /family и создай/присоединись.")
        return
    fam_id = row[0]

    # берём события за 48 часов
    since = datetime.utcnow() - timedelta(hours=48)
    q = (
        select(CareEvent, Baby.name)
        .join(Baby, CareEvent.baby_id == Baby.id, isouter=True)
        .where(CareEvent.family_id == fam_id, CareEvent.occurred_at >= since)
        .order_by(desc(CareEvent.occurred_at))
        .limit(50)
    )
    res = await session.execute(q)

    items = []
    for ce, baby_name in res.all():
        when = ce.occurred_at.strftime("%d.%m %H:%M")
        who = "кто-то"
        # для простоты не подгружаем User, можно расширить
        bname = f" ({baby_name})" if baby_name else ""
        details = f" – {ce.details}" if ce.details else ""
        items.append(f"{when} • {ce.type}{bname}{details}")

    if not items:
        await message.answer("Пока нет событий за 48 часов.")
        return

    await message.answer("📅 Семейный календарь (последние 48ч):\n" + "\n".join(items))
