import streamlit as st
import requests
import pandas as pd

# --- НАЛАШТУВАННЯ БЕЗПЕКИ ---
# Для базової версії задамо пароль прямо тут.
DOCTOR_PASSWORD = "medly_secure_2026"
API_URL = "http://127.0.0.1:8000"

# Налаштування сторінки (має бути найпершою командою)
st.set_page_config(page_title="BP-Monitor: Панель лікаря", page_icon="🩺", layout="wide")

# --- СИСТЕМА АВТОРИЗАЦІЇ ---
# Створюємо "коротку пам'ять", щоб запам'ятати, чи увійшов лікар
if "logged_in" not in st.session_state:
    st.session_state["logged_in"] = False

def check_password():
    """Функція для перевірки введеного пароля"""
    if st.session_state["password_input"] == DOCTOR_PASSWORD:
        st.session_state["logged_in"] = True
        st.session_state["password_input"] = "" # Очищуємо поле після входу
    else:
        st.error("❌ Невірний пароль! Доступ заборонено.")

# ---------------------------------------------------------
# ЕКРАН 1: ФОРМА ЛОГІНУ (Якщо лікар ще не увійшов)
# ---------------------------------------------------------
if not st.session_state["logged_in"]:
    # Робимо красиве вікно по центру екрана
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.title("🔒 Вхід у систему")
        st.markdown("Будь ласка, введіть пароль лікаря для доступу до медичних даних пацієнтів.")
        
        # Поле для пароля (символи будуть приховані зірочками)
        st.text_input("Пароль", type="password", key="password_input", on_change=check_password)
        st.button("Увійти", on_click=check_password, use_container_width=True)

# ---------------------------------------------------------
# ЕКРАН 2: ГОЛОВНА ПАНЕЛЬ ЛІКАРЯ (Якщо пароль правильний)
# ---------------------------------------------------------
else:
    # Кнопка виходу (розміщуємо справа вгорі)
    col1, col2 = st.columns([8, 1])
    with col1:
        st.title("🩺 Панель лікаря BP-Monitor")
    with col2:
        if st.button("🚪 Вийти", use_container_width=True):
            st.session_state["logged_in"] = False
            st.rerun() # Перезавантажуємо сторінку

    st.markdown("Тут ви можете контролювати показники артеріального тиску ваших пацієнтів.")

    # --- ЗАВАНТАЖЕННЯ ДАНИХ З API ---
    try:
        response = requests.get(f"{API_URL}/doctor/patients")
        
        if response.status_code == 200:
            patients = response.json()
            
            if not patients:
                st.info("У вашій базі поки немає пацієнтів. Зареєструйтесь через Telegram-бота!")
            else:
                st.subheader("👥 Список ваших пацієнтів")
                
                df = pd.DataFrame(patients)
                df = df.rename(columns={
                    "full_name": "ПІБ",
                    "telegram_id": "Telegram ID",
                    "last_sys": "Останній САТ",
                    "last_dia": "Останній ДАТ",
                    "is_critical": "Критичний стан?"
                })
                
                st.dataframe(df[["ПІБ", "Telegram ID", "Останній САТ", "Останній ДАТ", "Критичний стан?"]], use_container_width=True)
                
                st.divider()
                st.subheader("📊 Детальна історія замірів")
                
                selected_patient = st.selectbox(
                    "Оберіть пацієнта для перегляду історії:", 
                    patients, 
                    format_func=lambda x: x["full_name"]
                )
                
                if selected_patient:
                    hist_response = requests.get(f"{API_URL}/doctor/patients/{selected_patient['telegram_id']}/stats")
                    
                    if hist_response.status_code == 200:
                        stats = hist_response.json()
                        measurements = stats.get("measurements", [])
                        
                        if measurements:
                            hist_df = pd.DataFrame(measurements)
                            hist_df['created_at'] = pd.to_datetime(hist_df['created_at']).dt.strftime('%d.%m.%Y %H:%M')
                            hist_df = hist_df.rename(columns={
                                "created_at": "Дата і час",
                                "sys": "САТ (Верхній)",
                                "dia": "ДАТ (Нижній)",
                                "pulse": "Пульс",
                                "is_critical": "Критично"
                            })
                            st.table(hist_df[["Дата і час", "САТ (Верхній)", "ДАТ (Нижній)", "Пульс", "Критично"]])
                        else:
                            st.info("У цього пацієнта ще немає збережених замірів.")
        else:
            st.error(f"Помилка API: {response.status_code}")
    except requests.exceptions.ConnectionError:
        st.error("🚨 Не вдалося підключитися до API. Переконайтеся, що сервер Uvicorn працює в іншому терміналі!")