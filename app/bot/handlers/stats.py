from __future__ import annotations
from datetime import datetime, timedelta, date

from aiogram import Router, F, types

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_session
from app.db.models import User, Baby, SleepRecord, FeedingRecord
from app.utils.charts import bar_chart_png
from app.db.models import User, Baby, UserSettings  # + нужные модели раздела

router = Router(name="stats")

# --- helpers ---

async def _get_or_create_user(session: AsyncSession, tg: types.User) -> User:
    q = await session.execute(select(User).where(User.telegram_id == tg.id))
    user = q.scalar_one_or_none()
    if not user:
        user = User(
            telegram_id=tg.id,
            username=tg.username,
            first_name=tg.first_name,
            last_name=tg.last_name
        )
        session.add(user)
        await session.flush()
    return user

async def _get_primary_baby(session: AsyncSession, user_id: int) -> Baby | None:
    q = await session.execute(select(Baby).where(Baby.user_id == user_id).limit(1))
    return q.scalar_one_or_none()

def _last_7_days() -> list[date]:
    today = date.today()
    days = [today - timedelta(days=i) for i in range(6, -1, -1)]  # 7 дней: от -6 до 0
    return days

def _fmt_day(d: date) -> str:
    return d.strftime("%d.%m")

# --- callbacks ---

@router.callback_query(F.data == "stats_sleep_7d")
async def stats_sleep_7d(callback: types.CallbackQuery):
    days = _last_7_days()
    totals_minutes = {d: 0 for d in days}

    async for session in get_session():
        user = await _get_or_create_user(session, callback.from_user)
        baby = await _get_active_baby(session, user.id)
        if not baby:
            await callback.answer()
            await callback.message.answer("Нет данных: создайте профиль ребёнка и добавьте записи сна.")
            return

        # Для SQLite сгруппируем по дате sleep_start
        q = await session.execute(
            select(
                func.date(SleepRecord.sleep_start).label("d"),
                func.coalesce(func.sum(SleepRecord.duration_minutes), 0)
            )
            .where(
                SleepRecord.baby_id == baby.id,
                SleepRecord.sleep_start >= datetime.combine(days[0], datetime.min.time()),
                SleepRecord.sleep_start <= datetime.combine(days[-1], datetime.max.time()),
                SleepRecord.duration_minutes.is_not(None),
            )
            .group_by(func.date(SleepRecord.sleep_start))
        )
        rows = q.all()

    # Заполним словарь
    for d_str, total in rows:
        # d_str типа 'YYYY-MM-DD'
        d_obj = date.fromisoformat(d_str)
        if d_obj in totals_minutes:
            totals_minutes[d_obj] = int(total or 0)

    x = [_fmt_day(d) for d in days]
    vals_hours = [round(t / 60.0, 2) for t in [totals_minutes[d] for d in days]]  # в часы

    png = bar_chart_png(
        title="Сон за 7 дней (часы)",
        x_labels=x,
        values=vals_hours,
        ylabel="часы",
    )
    await callback.answer()
    await callback.message.answer_photo(types.BufferedInputFile(png.read(), filename="sleep_7d.png"))

@router.callback_query(F.data == "stats_feed_7d")
async def stats_feed_7d(callback: types.CallbackQuery):
    days = _last_7_days()
    totals_ml = {d: 0 for d in days}
    totals_g = {d: 0 for d in days}

    async for session in get_session():
        user = await _get_or_create_user(session, callback.from_user)
        baby = await _get_active_baby(session, user.id)
        if not baby:
            await callback.answer()
            await callback.message.answer("Нет данных: создайте профиль ребёнка и добавьте кормления.")
            return

        # Жидкости (ml): formula + water
        q_ml = await session.execute(
            select(
                func.date(FeedingRecord.fed_at).label("d"),
                func.coalesce(func.sum(FeedingRecord.amount_ml), 0)
            )
            .where(
                FeedingRecord.baby_id == baby.id,
                FeedingRecord.fed_at >= datetime.combine(days[0], datetime.min.time()),
                FeedingRecord.fed_at <= datetime.combine(days[-1], datetime.max.time()),
                FeedingRecord.amount_ml.is_not(None),
            )
            .group_by(func.date(FeedingRecord.fed_at))
        )
        rows_ml = q_ml.all()

        # Прикорм (g)
        q_g = await session.execute(
            select(
                func.date(FeedingRecord.fed_at).label("d"),
                func.coalesce(func.sum(FeedingRecord.amount_g), 0)
            )
            .where(
                FeedingRecord.baby_id == baby.id,
                FeedingRecord.fed_at >= datetime.combine(days[0], datetime.min.time()),
                FeedingRecord.fed_at <= datetime.combine(days[-1], datetime.max.time()),
                FeedingRecord.amount_g.is_not(None),
            )
            .group_by(func.date(FeedingRecord.fed_at))
        )
        rows_g = q_g.all()

    for d_str, total in rows_ml:
        d_obj = date.fromisoformat(d_str)
        if d_obj in totals_ml:
            totals_ml[d_obj] = int(total or 0)

    for d_str, total in rows_g:
        d_obj = date.fromisoformat(d_str)
        if d_obj in totals_g:
            totals_g[d_obj] = int(total or 0)

    x = [_fmt_day(d) for d in days]
    vals_ml = [totals_ml[d] for d in days]
    vals_g = [totals_g[d] for d in days]

    # Два отдельных графика: сначала мл, потом г (два сообщения)
    png_ml = bar_chart_png(
        title="Кормление (жидкость) за 7 дней, мл",
        x_labels=x,
        values=vals_ml,
        ylabel="мл",
    )
    png_g = bar_chart_png(
        title="Кормление (прикорм) за 7 дней, г",
        x_labels=x,
        values=vals_g,
        ylabel="г",
    )

    await callback.answer()
    await callback.message.answer_photo(types.BufferedInputFile(png_ml.read(), filename="feed_ml_7d.png"))
    await callback.message.answer_photo(types.BufferedInputFile(png_g.read(), filename="feed_g_7d.png"))
async def _get_active_baby(session: AsyncSession, user_id: int) -> Baby | None:
    # сначала пробуем активного
    qs = await session.execute(select(UserSettings).where(UserSettings.user_id == user_id))
    settings = qs.scalar_one_or_none()
    if settings and settings.active_baby_id:
        qb = await session.execute(select(Baby).where(Baby.id == settings.active_baby_id, Baby.user_id == user_id))
        baby = qb.scalar_one_or_none()
        if baby:
            return baby
    # иначе — первый по списку
    qb = await session.execute(select(Baby).where(Baby.user_id == user_id).order_by(Baby.id.asc()).limit(1))
    return qb.scalar_one_or_none()
