# app/db/models.py
from __future__ import annotations

from datetime import datetime, date

from sqlalchemy import (
    BigInteger,
    String,
    Integer,
    Date,
    DateTime,
    ForeignKey,
    Float,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


# Базовый класс для всех моделей
class Base(DeclarativeBase):
    pass


# --------- Пользователь ---------
class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    telegram_id: Mapped[int] = mapped_column(BigInteger, unique=True, index=True)
    username: Mapped[str | None] = mapped_column(String(255), nullable=True)
    first_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    last_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    babies: Mapped[list["Baby"]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
    )


# --------- Ребёнок ---------
class Baby(Base):
    __tablename__ = "babies"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(255))
    birth_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    # 'male' | 'female' | None
    gender: Mapped[str | None] = mapped_column(String(10), nullable=True)

    user: Mapped["User"] = relationship(back_populates="babies")
    sleep_records: Mapped[list["SleepRecord"]] = relationship(
        back_populates="baby",
        cascade="all, delete-orphan",
    )
    feeding_records: Mapped[list["FeedingRecord"]] = relationship(
        back_populates="baby",
        cascade="all, delete-orphan",
    )
    health_records: Mapped[list["HealthRecord"]] = relationship(
        back_populates="baby",
        cascade="all, delete-orphan",
    )


# --------- Настройки пользователя ---------
class UserSettings(Base):
    __tablename__ = "user_settings"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), unique=True, index=True)
    # активный ребёнок в UI (может быть None)
    active_baby_id: Mapped[int | None] = mapped_column(
        ForeignKey("babies.id", ondelete="SET NULL"),
        nullable=True,
    )


# --------- Сон ---------
class SleepRecord(Base):
    __tablename__ = "sleep_records"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    baby_id: Mapped[int] = mapped_column(ForeignKey("babies.id", ondelete="CASCADE"), index=True)
    sleep_start: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    sleep_end: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    duration_minutes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # 'good' | 'ok' | 'bad'
    quality: Mapped[str | None] = mapped_column(String(20), nullable=True)

    baby: Mapped["Baby"] = relationship(back_populates="sleep_records")


# --------- Кормление ---------
class FeedingRecord(Base):
    __tablename__ = "feeding_records"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    baby_id: Mapped[int] = mapped_column(ForeignKey("babies.id", ondelete="CASCADE"), index=True)
    fed_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    # 'breast' | 'formula' | 'water' | 'solid'
    feeding_type: Mapped[str] = mapped_column(String(20))
    amount_ml: Mapped[int | None] = mapped_column(Integer, nullable=True)
    amount_g: Mapped[int | None] = mapped_column(Integer, nullable=True)
    note: Mapped[str | None] = mapped_column(String(255), nullable=True)

    baby: Mapped["Baby"] = relationship(back_populates="feeding_records")


# --------- Здоровье ---------
class HealthRecord(Base):
    __tablename__ = "health_records"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    baby_id: Mapped[int] = mapped_column(ForeignKey("babies.id", ondelete="CASCADE"), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    # Тип: 'temperature' | 'medicine' | 'doctor_visit' | 'growth'
    record_type: Mapped[str] = mapped_column(String(20))

    # Температура (если есть)
    temperature_c: Mapped[float | None] = mapped_column(Float, nullable=True)

    # Лекарства (если есть)
    medicine_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    dose_mg: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Визит к врачу (если есть)
    visit_note: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # Рост/вес (если есть)
    height_cm: Mapped[int | None] = mapped_column(Integer, nullable=True)
    weight_g: Mapped[int | None] = mapped_column(Integer, nullable=True)

    baby: Mapped["Baby"] = relationship(back_populates="health_records")


# --------- Напоминания ---------
class Reminder(Base):
    __tablename__ = "reminders"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    chat_id: Mapped[int] = mapped_column(BigInteger, index=True)

    text: Mapped[str] = mapped_column(String(255))

    # Когда в следующий раз прислать напоминание
    next_run: Mapped[datetime] = mapped_column(DateTime, index=True)

    # Если None → одноразовое; иначе повтор каждые N минут
    interval_minutes: Mapped[int | None] = mapped_column(Integer, nullable=True)

    is_active: Mapped[bool] = mapped_column(default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
# --- Семья, участники, инвайты, журнал событий (календарь) ---

from uuid import uuid4
from sqlalchemy import UniqueConstraint, Text, Boolean

class Family(Base):
    __tablename__ = "families"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    title: Mapped[str] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    members: Mapped[list["FamilyMember"]] = relationship(
        back_populates="family",
        cascade="all, delete-orphan",
    )
    invites: Mapped[list["FamilyInvite"]] = relationship(
        back_populates="family",
        cascade="all, delete-orphan",
    )


class FamilyMember(Base):
    __tablename__ = "family_members"
    __table_args__ = (
        UniqueConstraint("family_id", "user_id", name="uq_family_user"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    family_id: Mapped[int] = mapped_column(ForeignKey("families.id", ondelete="CASCADE"), index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)

    # role: 'owner' | 'parent' | 'nanny'
    role: Mapped[str] = mapped_column(String(20), default="parent")

    family: Mapped["Family"] = relationship(back_populates="members")


class FamilyInvite(Base):
    __tablename__ = "family_invites"
    __table_args__ = (
        UniqueConstraint("code", name="uq_invite_code"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    family_id: Mapped[int] = mapped_column(ForeignKey("families.id", ondelete="CASCADE"), index=True)
    code: Mapped[str] = mapped_column(String(64), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    family: Mapped["Family"] = relationship(back_populates="invites")


class CareEvent(Base):
    """
    Унифицированное событие для календаря семьи: кто/что/когда/для какого ребёнка.
    type: 'sleep_start' | 'sleep_end' | 'feeding' | 'bath' | 'medicine' | ...
    details: произвольный текст (например: 'formula 120 ml' или 'сон 45 мин')
    """
    __tablename__ = "care_events"
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    family_id: Mapped[int | None] = mapped_column(ForeignKey("families.id", ondelete="SET NULL"), index=True, nullable=True)
    baby_id: Mapped[int | None] = mapped_column(ForeignKey("babies.id", ondelete="SET NULL"), index=True, nullable=True)
    actor_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), index=True, nullable=True)

    occurred_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
    type: Mapped[str] = mapped_column(String(32))
    details: Mapped[str | None] = mapped_column(Text, nullable=True)

    # связи (по желанию)
    # family: relationship("Family")
    # baby: relationship("Baby")
