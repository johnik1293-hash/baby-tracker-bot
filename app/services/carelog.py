# app/services/carelog.py
from __future__ import annotations
from datetime import datetime, timezone
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.models import CareEvent, FamilyMember, UserSettings

async def get_user_family_id(session: AsyncSession, user_id: int) -> int | None:
    q = select(FamilyMember.family_id).where(FamilyMember.user_id == user_id)
    res = await session.execute(q)
    row = res.first()
    return row[0] if row else None

async def get_active_baby_id(session: AsyncSession, user_id: int) -> int | None:
    q = select(UserSettings.active_baby_id).where(UserSettings.user_id == user_id)
    res = await session.execute(q)
    row = res.first()
    return row[0] if row else None

async def log_event(
    session: AsyncSession,
    *,
    actor_user_id: int,
    event_type: str,
    details: str | None = None,
    occurred_at: datetime | None = None,
    baby_id: int | None = None,
) -> CareEvent:
    family_id = await get_user_family_id(session, actor_user_id)
    if baby_id is None:
        baby_id = await get_active_baby_id(session, actor_user_id)

    if occurred_at is None:
        occurred_at = datetime.now(timezone.utc).replace(tzinfo=None)  # храним naive UTC в DateTime

    ce = CareEvent(
        family_id=family_id,
        baby_id=baby_id,
        actor_user_id=actor_user_id,
        occurred_at=occurred_at,
        type=event_type,
        details=details,
    )
    session.add(ce)
    await session.commit()
    return ce
