from fastapi import FastAPI, HTTPException, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel, ConfigDict
from typing import List, Optional
import uuid
from datetime import datetime

# Імпортуємо нашу базу даних
from database import async_session, User, Measurement, UserRole

app = FastAPI(title="BP-Monitor Doctor API")

# =====================================================================
# 1. PYDANTIC СХЕМИ (Те, чого не вистачало у вашому коді)
# Вони відповідають за те, щоб красиво пакувати дані для браузера
# =====================================================================

class PatientSummary(BaseModel):
    id: uuid.UUID
    full_name: str
    telegram_id: int
    target_sys: int
    target_dia: int
    last_sys: Optional[int] = None
    last_dia: Optional[int] = None
    is_critical: bool = False

    model_config = ConfigDict(from_attributes=True)

class MeasurementEntry(BaseModel):
    id: uuid.UUID
    sys: int
    dia: int
    pulse: int
    comment: Optional[str] = None
    created_at: datetime
    is_critical: bool = False

    model_config = ConfigDict(from_attributes=True)

class PatientStats(BaseModel):
    id: uuid.UUID
    full_name: str
    telegram_id: int
    target_sys: int
    target_dia: int
    measurements: List[MeasurementEntry]

    model_config = ConfigDict(from_attributes=True)

# =====================================================================
# 2. РОУТЕРИ (Адаптований ваш код)
# =====================================================================

@app.get("/")
async def root():
    return {"message": "Doctor API працює! Перейдіть на /docs для тестування."}

@app.get("/doctor/patients", response_model=List[PatientSummary], tags=["doctor"])
async def list_patients(
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200)
):
    """
    Повертає список усіх пацієнтів (Поки що без перевірки JWT токена лікаря)
    """
    async with async_session() as session:
        # Шукаємо всіх пацієнтів
        result = await session.execute(
            select(User).where(User.role == UserRole.patient).offset(skip).limit(limit)
        )
        patients = result.scalars().all()

        summaries = []
        for patient in patients:
            # Шукаємо останній замір для кожного пацієнта
            meas_result = await session.execute(
                select(Measurement)
                .where(Measurement.user_id == patient.id)
                .order_by(Measurement.created_at.desc())
                .limit(1)
            )
            last = meas_result.scalar_one_or_none()

            # Визначаємо, чи критичний стан
            is_crit = False
            if last and (last.sys > 140 or last.dia > 90):
                is_crit = True

            summaries.append(
                PatientSummary(
                    id=patient.id,
                    full_name=patient.full_name,
                    telegram_id=patient.telegram_id,
                    target_sys=patient.target_sys,
                    target_dia=patient.target_dia,
                    last_sys=last.sys if last else None,
                    last_dia=last.dia if last else None,
                    is_critical=is_crit
                )
            )
        return summaries

@app.get("/doctor/patients/{telegram_id}/stats", response_model=PatientStats, tags=["doctor"])
async def get_patient_stats(
    telegram_id: int,
    limit: int = Query(default=100, ge=1, le=500)
):
    """
    Повертає повну історію конкретного пацієнта (за його Telegram ID)
    """
    async with async_session() as session:
        # Шукаємо пацієнта
        user_result = await session.execute(select(User).where(User.telegram_id == telegram_id))
        patient = user_result.scalar_one_or_none()

        if not patient:
            raise HTTPException(status_code=404, detail="Пацієнта не знайдено")

        # Шукаємо його історію
        m_result = await session.execute(
            select(Measurement)
            .where(Measurement.user_id == patient.id)
            .order_by(Measurement.created_at.desc())
            .limit(limit)
        )
        measurements = m_result.scalars().all()

        entries = []
        for m in measurements:
            is_crit = m.sys > 140 or m.dia > 90
            entries.append(
                MeasurementEntry(
                    id=m.id,
                    sys=m.sys,
                    dia=m.dia,
                    pulse=m.pulse,
                    comment=m.comment,
                    created_at=m.created_at,
                    is_critical=is_crit
                )
            )

        return PatientStats(
            id=patient.id,
            full_name=patient.full_name,
            telegram_id=patient.telegram_id,
            target_sys=patient.target_sys,
            target_dia=patient.target_dia,
            measurements=entries
        )