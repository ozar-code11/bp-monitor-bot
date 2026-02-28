from typing import Optional  # ДОДАНО: спеціальний інструмент для необов'язкових значень
import enum
import uuid
from datetime import datetime, time, timezone

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    String,
    Text,
    Time,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship, declarative_base
from sqlalchemy.sql import func
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

# ── 1. Налаштування підключення до SQLite ──────────────────────────────
engine = create_async_engine("postgresql+asyncpg://neondb_ownernpg_b6eYaODK3pFT@ep-restless-mud-aift3ear-pooler.c-4.us-east-1.aws.neon.techneondbsslmode=require&channel_binding=require", echo=False)
Base = declarative_base()

async_session = sessionmaker(
    engine, class_=AsyncSession, expire_on_commit=False
)

async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

# ── 2. Перерахування ───────────────────────────────────────────────────
class UserRole(str, enum.Enum):
    patient = "patient"
    doctor  = "doctor"

# ── 3. Таблиця Користувачів (Лікарі та Пацієнти) ───────────────────────
class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        index=True,
    )

    telegram_id: Mapped[int] = mapped_column(
        BigInteger,
        unique=True,
        nullable=False,
        index=True,
    )

    full_name: Mapped[str] = mapped_column(String(255), nullable=False)

    role: Mapped[UserRole] = mapped_column(
        Enum(UserRole, name="user_role"),
        nullable=False,
        default=UserRole.patient,
    )

    # ВИПРАВЛЕНО: Використовуємо Optional
    doctor_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    target_sys: Mapped[int] = mapped_column(Integer, nullable=False, default=120)
    target_dia: Mapped[int] = mapped_column(Integer, nullable=False, default=80)

    # ВИПРАВЛЕНО: Використовуємо Optional замість | None
    doctor: Mapped[Optional["User"]] = relationship(
        "User",
        back_populates="patients",
        foreign_keys=[doctor_id],
        remote_side="User.id",
    )

    patients: Mapped[list["User"]] = relationship(
        "User",
        back_populates="doctor",
        foreign_keys=[doctor_id],
    )

    measurements: Mapped[list["Measurement"]] = relationship(
        "Measurement",
        back_populates="user",
        cascade="all, delete-orphan",
        lazy="select",
    )

    reminders: Mapped[list["Reminder"]] = relationship(
        "Reminder",
        back_populates="user",
        cascade="all, delete-orphan",
        lazy="select",
    )

# ── 4. Таблиця Замірів Тиску ───────────────────────────────────────────
class Measurement(Base):
    __tablename__ = "measurements"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        index=True,
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    sys: Mapped[int] = mapped_column(Integer, nullable=False)
    dia: Mapped[int] = mapped_column(Integer, nullable=False)
    pulse: Mapped[int] = mapped_column(Integer, nullable=False)
    
    # ВИПРАВЛЕНО
    comment: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        default=lambda: datetime.now(timezone.utc),
    )

    user: Mapped[User] = relationship("User", back_populates="measurements")

# ── 5. Таблиця Нагадувань ──────────────────────────────────────────────
class Reminder(Base):
    __tablename__ = "reminders"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        index=True,
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    time: Mapped[time] = mapped_column(Time, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    user: Mapped[User] = relationship("User", back_populates="reminders")