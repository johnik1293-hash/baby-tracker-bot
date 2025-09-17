from __future__ import annotations
from datetime import datetime, date

from sqlalchemy import BigInteger, String, Integer, Date, DateTime, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.database import Base

class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    telegram_id: Mapped[int] = mapped_column(BigInteger, unique=True, index=True)
    username: Mapped[str | None] = mapped_column(String(255), nullable=True)
    first_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    last_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    babies: Mapped[list["Baby"]] = relationship(back_populates="user", cascade="all, delete-orphan")

class Baby(Base):
    __tablename__ = "babies"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(255))
    birth_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    gender: Mapped[str | None] = mapped_column(String(10), nullable=True)  # 'male' | 'female' | None

    user: Mapped["User"] = relationship(back_populates="babies")
    sleep_records: Mapped[list["SleepRecord"]] = relationship(back_populates="baby", cascade="all, delete-orphan")
    feeding_records: Mapped[list["FeedingRecord"]] = relationship(back_populates="baby", cascade="all, delete-orphan")
    health_records: Mapped[list["HealthRecord"]] = relationship(back_populates="baby", cascade="all, delete-orphan")

class UserSettings(Base):
    __tablename__ = "user_settings"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), unique=True, index=True)
    active_baby_id: Mapped[int | None] = mapped_column(ForeignKey("babies.id", ondelete="SET NULL"), nullable=True)


class SleepRecord(Base):
    __tablename__ = "sleep_records"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    baby_id: Mapped[int] = mapped_column(ForeignKey("babies.id", ondelete="CASCADE"), index=True)
    sleep_start: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    sleep_end: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    duration_minutes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    quality: Mapped[str | None] = mapped_column(String(20), nullable=True)  # 'good' | 'ok' | 'bad'

    baby: Mapped["Baby"] = relationship(back_populates="sleep_records")

class FeedingRecord(Base):
    __tablename__ = "feeding_records"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    baby_id: Mapped[int] = mapped_column(ForeignKey("babies.id", ondelete="CASCADE"), index=True)
    fed_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    feeding_type: Mapped[str] = mapped_column(String(20))  # 'breast'|'formula'|'water'|'solid'
    amount_ml: Mapped[int | None] = mapped_column(Integer, nullable=True)
    amount_g: Mapped[int | None] = mapped_column(Integer, nullable=True)
    note: Mapped[str | None] = mapped_column(String(255), nullable=True)

    baby: Mapped["Baby"] = relationship(back_populates="feeding_records")

class HealthRecord(Base):
    __tablename__ = "health_records"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    baby_id: Mapped[int] = mapped_column(ForeignKey("babies.id", ondelete="CASCADE"), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # Тип записи: 'temperature' | 'medicine' | 'doctor_visit' | 'growth'
    record_type: Mapped[str] = mapped_column(String(20))

    # Температура (если есть)
    temperature_c: Mapped[float | None] = mapped_column(nullable=True)

    # Лекарства (если есть)
    medicine_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    dose_mg: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Визит к врачу (если есть)
    visit_note: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # Рост/вес (если есть)
    height_cm: Mapped[int | None] = mapped_column(Integer, nullable=True)
    weight_g: Mapped[int | None] = mapped_column(Integer, nullable=True)

    baby: Mapped["Baby"] = relationship(back_populates="health_records")

class Reminder(Base):
    __tablename__ = "reminders"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    chat_id: Mapped[int] = mapped_column(BigInteger, index=True)

    text: Mapped[str] = mapped_column(String(255))

    # Когда в следующий раз прислать напоминание (UTC времени движка; для SQLite — локальное)
    next_run: Mapped[datetime] = mapped_column(DateTime, index=True)

    # Если None → одноразовое. Если задано → период в минутах (повторяющееся)
    interval_minutes: Mapped[int | None] = mapped_column(Integer, nullable=True)

    is_active: Mapped[bool] = mapped_column(default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # отношения (не обязательно использовать прямо сейчас)
    # user: Mapped["User"] = relationship()

