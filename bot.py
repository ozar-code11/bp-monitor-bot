import asyncio
from datetime import datetime
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import CommandStart, Command  # ДОДАНО: Command для нових команд
from sqlalchemy import select, desc  # ДОДАНО: desc для сортування за датою
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from database import init_db, async_session, User, Measurement, UserRole

# ВСТАВТЕ СВІЙ ТОКЕН ТУТ:
TOKEN = "8692403827:AAFtHx5VKPn8KYH6M4-vBgVL41nW_UPybD8"

bot = Bot(token=TOKEN)
dp = Dispatcher()
#  ФУНКЦІЯ НАГАДУВАННЯ (має бути тут, перед запуском бота)
# -------------------------------------------------------------------
async def send_daily_reminders():
    print(f"⏰ [{datetime.now().strftime('%H:%M')}] Перевірка бази для нагадувань...")
    async with async_session() as session:
        # Отримуємо всіх пацієнтів
        result = await session.execute(select(User).where(User.role == UserRole.patient))
        patients = result.scalars().all()
        
        today = datetime.now().date()
        
        for patient in patients:
            # Перевіряємо, чи були записи від цього пацієнта сьогодні
            stmt = select(Measurement).where(Measurement.user_id == patient.id)
            m_result = await session.execute(stmt)
            measurements = m_result.scalars().all()
            
            has_measured_today = any(m.created_at.date() == today for m in measurements)
            
            # Якщо сьогодні записів ще не було — нагадуємо
            if not has_measured_today:
                try:
                    await bot.send_message(
                        chat_id=patient.telegram_id,
                        text="🔔 Ви сьогодні ще не записували показники тиску. Будь ласка, зробіть це!"
                    )
                    print(f"✅ Надіслано нагадування для: {patient.full_name}")
                except Exception as e:
                    print(f"❌ Не вдалося написати {patient.full_name}: {e}")


# 1. Реєстрація (/start)
@dp.message(CommandStart())
async def command_start_handler(message: types.Message):
    async with async_session() as session:
        stmt = select(User).where(User.telegram_id == message.from_user.id)
        result = await session.execute(stmt)
        user = result.scalar_one_or_none()

        if user is None:
            new_user = User(
                telegram_id=message.from_user.id,
                full_name=message.from_user.full_name,
                role=UserRole.patient
            )
            session.add(new_user)
            await session.commit()
    
    text = (
        f"Привіт, {message.from_user.full_name}! 👋\n\n"
        f"Я ваш особистий щоденник тиску.\n"
        f"🔹 Щоб записати дані, відправте 3 цифри: 120 80 70\n"
        f"🔹 Щоб подивитися історію, натисніть /history"
    )
    await message.answer(text)

# 2. Перегляд історії (/history)
@dp.message(Command("history"))
async def command_history_handler(message: types.Message):
    async with async_session() as session:
        # Знаходимо користувача
        stmt_user = select(User).where(User.telegram_id == message.from_user.id)
        result_user = await session.execute(stmt_user)
        user = result_user.scalar_one_or_none()

        if user is None:
            await message.answer("❌ Ви ще не зареєстровані. Натисніть /start")
            return

        # Шукаємо останні 5 замірів цього користувача
        stmt_meas = (
            select(Measurement)
            .where(Measurement.user_id == user.id)
            .order_by(desc(Measurement.created_at)) # Сортуємо від нових до старих
            .limit(5) # Беремо лише 5 штук
        )
        result_meas = await session.execute(stmt_meas)
        measurements = result_meas.scalars().all()

        if not measurements:
            await message.answer("У вас ще немає збережених записів. Відправте мені свої показники (наприклад: 120 80 70).")
            return

        # Формуємо гарне повідомлення з результатами
        text = "📊 **Ваші останні 5 замірів:**\n\n"
        for m in measurements:
            # Форматуємо дату (день.місяць.рік години:хвилини)
            date_str = m.created_at.strftime("%d.%m.%Y %H:%M")
            text += f"📅 {date_str} | 🩸 {m.sys}/{m.dia} | ❤️ {m.pulse}\n"

        await message.answer(text, parse_mode="Markdown")

# 3. Збереження даних (цифри)
@dp.message(F.text)
async def handle_bp_data(message: types.Message):
    text = message.text.strip()
    parts = text.split()
    
    if len(parts) == 3 and all(p.isdigit() for p in parts):
        sys = int(parts[0])
        dia = int(parts[1])
        pulse = int(parts[2])
        
        async with async_session() as session:
            stmt = select(User).where(User.telegram_id == message.from_user.id)
            result = await session.execute(stmt)
            user = result.scalar_one_or_none()
            
            if user is None:
                await message.answer("❌ Будь ласка, спочатку натисніть /start для реєстрації.")
                return
            
            new_measurement = Measurement(user_id=user.id, sys=sys, dia=dia, pulse=pulse)
            session.add(new_measurement)
            await session.commit()

        warning = ""
        if sys >= 140 or dia >= 90:
            warning = "\n\n⚠️ Увага: Ваш тиск вище норми."
            
        await message.answer(f"✅ Дані збережено!\n🩸 Тиск: {sys}/{dia}\n❤️ Пульс: {pulse}{warning}")
    else:
        await message.answer("❌ Введіть рівно 3 числа через пробіл.\nНаприклад: 120 80 70")

async def main():
    print("Ініціалізація бази даних...")
    await init_db()
    print("Бот успішно запущено! Очікую показники...")
    await dp.start_polling(bot)
#

# -------------------------------------------------------------------
# ЗАПУСК БОТА ТА ПЛАНУВАЛЬНИКА
# -------------------------------------------------------------------
async def main():
    await init_db()
    
    # Вмикаємо "будильник"
    scheduler = AsyncIOScheduler(timezone="Europe/Kyiv")
    
    # НОВИЙ РЯДОК: Спрацьовуватиме щодня рівно о 19:00 за Києвом
    scheduler.add_job(send_daily_reminders, trigger='cron', hour=19, minute=0)
    
    scheduler.start()
    print("⏰ Планувальник запущено (перевірка о 19:00)!")

    print("Бот успішно запущено! Очікую повідомлення...")
    await dp.start_polling(bot)

if __name__ == "__main__":

    asyncio.run(main())

