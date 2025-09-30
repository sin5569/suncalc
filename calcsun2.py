import streamlit as st
import requests
import pandas as pd
import matplotlib.pyplot as plt
import folium
from streamlit_folium import st_folium
import math
import time
from datetime import datetime

# Настройка страницы
st.set_page_config(layout="wide", page_title="☀️ Солнечная генерация")
st.title("☀️ Динамический калькулятор солнечной генерации")

# ===== КЭШИРОВАНИЕ ДАННЫХ =====
@st.cache_data(ttl=3600)  # Кэш на 1 час
def get_pvgis_data(lat, lon, tilt, peak_power, azimuth):
    """Получение данных от PVGIS API с кэшированием"""
    url = (
        f"https://re.jrc.ec.europa.eu/api/PVcalc?"
        f"lat={lat}&lon={lon}&peakpower={peak_power}&loss=14&angle={tilt}&azimuth={azimuth}&outputformat=json"
    )
    try:
        response = requests.get(url, timeout=15)
        if response.status_code == 200:
            return response.json()
        else:
            st.error(f"Ошибка PVGIS API: {response.status_code}")
            return None
    except requests.exceptions.RequestException as e:
        st.error(f"Ошибка запроса к PVGIS: {e}")
        return None

# ===== СИДЕБАР - ПАРАМЕТРЫ СИСТЕМЫ =====
st.sidebar.header("📍 Локация и ориентация панелей")

# Быстрый выбор городов
cities = {
    "Полтава": (49.5883, 34.5514),
    "Киев": (50.4500, 30.5233),
    "Львов": (49.8425, 24.0322),
    "Одесса": (46.4825, 30.7233),
    "Харьков": (49.9935, 36.2304),
    "Днепр": (48.4647, 35.0462)
}

selected_city = st.sidebar.selectbox("Быстрый выбор города:", list(cities.keys()))
city_lat, city_lon = cities[selected_city]

# Точная настройка координат
col1, col2 = st.sidebar.columns(2)
with col1:
    lat = st.number_input("Широта", value=city_lat, format="%.6f", key="lat")
with col2:
    lon = st.number_input("Долгота", value=city_lon, format="%.6f", key="lon")

# Направления панелей
directions = {
    "Север": 180,
    "Северо-Восток": 135,
    "Восток": 270,
    "Юго-Восток": 315,
    "Юг": 0,
    "Юго-Запад": 45,
    "Запад": 90,
    "Северо-Запад": 225
}

direction = st.sidebar.selectbox("Ориентация панели:", list(directions.keys()))
azimuth = directions[direction]

# Угол наклона с предустановками
tilt_presets = {
    "Оптимальный (широта)": round(lat),
    "Плоская (0°)": 0,
    "Пологая (15°)": 15,
    "Средняя (30°)": 30,
    "Крутая (45°)": 45,
    "Вертикальная (90°)": 90
}

tilt_preset = st.sidebar.selectbox("Предустановки наклона:", list(tilt_presets.keys()))
tilt = st.sidebar.slider("Точная настройка угла наклона (°)", 0, 90, tilt_presets[tilt_preset])

# Мощность системы
peak_power = st.sidebar.slider("Установленная мощность системы (кВт)", 1.0, 100.0, 5.0, 0.1)

# ===== ИНДИКАТОР ЗАГРУЗКИ =====
with st.spinner("Получение данных от PVGIS..."):
    data = get_pvgis_data(lat, lon, tilt, peak_power, azimuth)

# ===== ОБРАБОТКА ДАННЫХ =====
def parse_pvgis_data(data):
    """Парсинг и обработка данных PVGIS"""
    if not data or "outputs" not in data:
        return None
    
    monthly = data["outputs"]["monthly"]["fixed"]
    df = pd.DataFrame(monthly)
    
    # Добавляем русские названия месяцев
    months_ru = ["Янв", "Фев", "Мар", "Апр", "Май", "Июн", 
                "Июл", "Авг", "Сен", "Окт", "Ноя", "Дек"]
    df["month"] = months_ru
    
    # Переименовываем колонки для понятности
    df = df.rename(columns={
        "E_m": "Генерация_кВтч",
        "H(i)_m": "Солнечная_радиация",
        "SD_m": "Стандартное_отклонение"
    })
    
    return df

df = parse_pvgis_data(data)

# ===== ОСНОВНОЙ ИНТЕРФЕЙС =====
if df is not None:
    # ===== КАРТА =====
    st.subheader("🗺️ Местоположение и направление панели")
    
    # Создаем карту
    m = folium.Map(location=[lat, lon], zoom_start=15)
    
    # Расчет направления стрелки
    angle_rad = math.radians(azimuth)
    lat_offset = round(0.001 * math.cos(angle_rad), 6)
    lon_offset = round(0.001 * math.sin(angle_rad), 6)
    
    # Маркер установки
    folium.Marker(
        [lat, lon],
        tooltip=f"Установка: {direction}, {tilt}°",
        popup=f"Мощность: {peak_power} кВт",
        icon=folium.Icon(color="blue", icon="sun", prefix="fa")
    ).add_to(m)
    
    # Стрелка направления
    folium.PolyLine(
        locations=[[lat, lon], [lat + lat_offset, lon + lon_offset]],
        color="red",
        weight=4,
        tooltip=f"Направление: {direction}",
        opacity=0.8
    ).add_to(m)
    
    # Отображаем карту
    st_folium(m, width=800, height=400)
    
    # ===== СВОДКА ПОКАЗАТЕЛЕЙ =====
    st.subheader("📊 Сводка показателей")
    
    total_generation = df["Генерация_кВтч"].sum()
    avg_generation = df["Генерация_кВтч"].mean()
    max_month = df.loc[df["Генерация_кВтч"].idxmax(), "month"]
    min_month = df.loc[df["Генерация_кВтч"].idxmin(), "month"]
    max_generation = df["Генерация_кВтч"].max()
    min_generation = df["Генерация_кВтч"].min()
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("Общая годовая генерация", f"{total_generation:.0f} кВт·ч")
    with col2:
        st.metric("Средняя месячная", f"{avg_generation:.0f} кВт·ч")
    with col3:
        st.metric("Лучший месяц", f"{max_month} ({max_generation:.0f} кВт·ч)")
    with col4:
        st.metric("Худший месяц", f"{min_month} ({min_generation:.0f} кВт·ч)")
    
    # ===== ГРАФИК =====
    st.subheader("📈 Динамика генерации по месяцам")
    
    fig, ax = plt.subplots(figsize=(12, 6))
    
    # График генерации
    bars = ax.bar(df["month"], df["Генерация_кВтч"], 
                 color=plt.cm.viridis(df["Генерация_кВтч"] / df["Генерация_кВтч"].max()),
                 alpha=0.7,
                 edgecolor='black',
                 linewidth=0.5)
    
    # Линия тренда
    ax.plot(df["month"], df["Генерация_кВтч"], 'r-', alpha=0.5, linewidth=2, marker='o')
    
    ax.set_ylabel("Выработка (кВт·ч/мес)", fontsize=12)
    ax.set_xlabel("Месяцы", fontsize=12)
    ax.set_title(f"Генерация солнечной электростанции\nНаправление: {direction}, Наклон: {tilt}°, Мощность: {peak_power} кВт", 
                 fontsize=14, fontweight='bold')
    ax.grid(True, alpha=0.3)
    
    # Добавляем значения на столбцы
    for bar in bars:
        height = bar.get_height()
        ax.text(bar.get_x() + bar.get_width()/2., height + max_generation*0.01,
               f'{height:.0f}', ha='center', va='bottom', fontsize=9)
    
    # Настройка внешнего вида
    plt.xticks(rotation=45)
    plt.tight_layout()
    st.pyplot(fig)
    
    # ===== ТАБЛИЦА ПОД ГРАФИКОМ =====
    st.subheader("📋 Детальные данные по месяцам")
    
    # Форматируем таблицу для отображения
    display_df = df.copy()
    display_df["Генерация_кВтч"] = display_df["Генерация_кВтч"].round(1)
    display_df["Солнечная_радиация"] = display_df["Солнечная_радиация"].round(1)
    display_df["Стандартное_отклонение"] = display_df["Стандартное_отклонение"].round(1)
    
    # Переименовываем колонки для лучшего отображения
    display_df = display_df.rename(columns={
        "month": "Месяц",
        "Генерация_кВтч": "Генерация (кВт·ч)",
        "Солнечная_радиация": "Солнечная радиация (кВт·ч/м²)",
        "Стандартное_отклонение": "Стандартное отклонение"
    })
    
    # Отображаем таблицу
    st.dataframe(display_df, use_container_width=True, hide_index=True)
    
    # ===== ДОПОЛНИТЕЛЬНАЯ ИНФОРМАЦИЯ =====
    with st.expander("📊 Детальная статистика и эффективность"):
        col1, col2 = st.columns(2)
        
        with col1:
            st.write("**📈 Статистика генерации:**")
            st.write(f"- Максимальная месячная генерация: **{max_generation:.1f} кВт·ч**")
            st.write(f"- Минимальная месячная генерация: **{min_generation:.1f} кВт·ч**")
            st.write(f"- Стандартное отклонение: **{df['Генерация_кВтч'].std():.1f} кВт·ч**")
            st.write(f"- Коэффициент вариации: **{(df['Генерация_кВтч'].std() / avg_generation) * 100:.1f}%**")
            
        with col2:
            st.write("**⚡ Эффективность системы:**")
            efficiency = (total_generation / (peak_power * 365)) * 100
            capacity_factor = (total_generation / (peak_power * 8760)) * 100
            st.write(f"- Средний дневной yield: **{total_generation / 365:.1f} кВт·ч/день**")
            st.write(f"- Коэффициент использования (CUF): **{capacity_factor:.1f}%**")
            st.write(f"- Удельная генерация: **{total_generation / peak_power:.0f} кВт·ч/кВт**")
            st.write(f"- Эффективность системы: **{efficiency:.1f}%**")
    
    # ===== СОВЕТЫ ПО ОПТИМИЗАЦИИ =====
    with st.expander("💡 Рекомендации по оптимизации"):
        st.write("**Для улучшения генерации рассмотрите:**")
        
        if direction != "Юг":
            st.write(f"- 🔄 Изменение ориентации с **{direction}** на **Юг** может увеличить генерацию")
        
        optimal_tilt = round(lat)
        if abs(tilt - optimal_tilt) > 10:
            st.write(f"- 📐 Корректировка угла наклона с **{tilt}°** на **{optimal_tilt}°** (оптимальный для широты)")
        
        if capacity_factor < 15:
            st.write(f"- ⚡ Рассмотрите увеличение мощности системы для лучшей окупаемости")
        
        st.write(f"- 📅 Наибольшая генерация ожидается в **{max_month}** - планируйте обслуживание")
    
else:
    st.error("❌ Не удалось получить данные от PVGIS. Проверьте параметры и подключение к интернету.")

# ===== ФУТЕР =====
st.markdown("---")
st.markdown("*Данные предоставлены PVGIS API • Координаты по умолчанию: Полтава, Украина*")
