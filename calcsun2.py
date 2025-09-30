import streamlit as st
import requests
import pandas as pd
import matplotlib.pyplot as plt
import folium
from streamlit_folium import st_folium
import math
import numpy as np
from datetime import datetime, timedelta

# Настройка страницы
st.set_page_config(layout="wide", page_title="☀️ Солнечная генерация")
st.title("☀️ Динамический калькулятор солнечной генерации")

# ===== КЭШИРОВАНИЕ ДАННЫХ =====
@st.cache_data(ttl=3600)  # Кэш на 1 час
def get_pvgis_data(lat, lon, tilt, peak_power, azimuth, start_year=2020, end_year=2020):
    """Получение данных от PVGIS API с кэшированием"""
    url = (
        f"https://re.jrc.ec.europa.eu/api/v5_2/seriescalc?"
        f"lat={lat}&lon={lon}&peakpower={peak_power}&loss=14&angle={tilt}&azimuth={azimuth}"
        f"&startyear={start_year}&endyear={end_year}&outputformat=json"
    )
    try:
        response = requests.get(url, timeout=20)
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
with st.spinner("Получение почасовых данных от PVGIS..."):
    data = get_pvgis_data(lat, lon, tilt, peak_power, azimuth)

# ===== ОБРАБОТКА ДАННЫХ =====
def parse_pvgis_hourly_data(data):
    """Парсинг почасовых данных PVGIS"""
    if not data or "outputs" not in data:
        return None
    
    hourly_data = data["outputs"]["hourly"]
    df = pd.DataFrame(hourly_data)
    
    # Преобразуем время
    df['time'] = pd.to_datetime(df['time'], format='%Y%m%d:%H%M')
    df['date'] = df['time'].dt.date
    df['month'] = df['time'].dt.month
    df['week'] = df['time'].dt.isocalendar().week
    df['hour'] = df['time'].dt.hour
    df['day_of_year'] = df['time'].dt.dayofyear
    
    return df

def calculate_periods_generation(df, peak_power):
    """Расчет генерации за разные периоды"""
    if df is None:
        return None
    
    # Почасовая генерация
    hourly = df.groupby(['date', 'hour'])['P'].sum().reset_index()
    
    # Дневная генерация
    daily = df.groupby('date')['P'].sum().reset_index()
    daily['P'] = daily['P'] / 1000  # Переводим в кВт·ч
    
    # Недельная генерация
    weekly = df.groupby('week')['P'].sum().reset_index()
    weekly['P'] = weekly['P'] / 1000  # Переводим в кВт·ч
    
    # Месячная генерация
    monthly = df.groupby('month')['P'].sum().reset_index()
    monthly['P'] = monthly['P'] / 1000  # Переводим в кВт·ч
    
    # Годовая генерация
    yearly_total = df['P'].sum() / 1000  # Переводим в кВт·ч
    
    # Средние показатели
    avg_hourly = df['P'].mean() / 1000  # кВт·ч
    avg_daily = daily['P'].mean()
    avg_weekly = weekly['P'].mean()
    avg_monthly = monthly['P'].mean()
    
    return {
        'hourly': hourly,
        'daily': daily,
        'weekly': weekly,
        'monthly': monthly,
        'yearly_total': yearly_total,
        'avg_hourly': avg_hourly,
        'avg_daily': avg_daily,
        'avg_weekly': avg_weekly,
        'avg_monthly': avg_monthly,
        'raw_data': df
    }

df_hourly = parse_pvgis_hourly_data(data)
periods_data = calculate_periods_generation(df_hourly, peak_power) if df_hourly is not None else None

# ===== ОСНОВНОЙ ИНТЕРФЕЙС =====
if periods_data is not None:
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
    
    # ===== СВОДКА ПОКАЗАТЕЛЕЙ ВСЕХ ПЕРИОДОВ =====
    st.subheader("📊 Сводка генерации за все периоды")
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("Годовая генерация", f"{periods_data['yearly_total']:.0f} кВт·ч")
        st.metric("Средняя месячная", f"{periods_data['avg_monthly']:.0f} кВт·ч")
    
    with col2:
        st.metric("Средняя недельная", f"{periods_data['avg_weekly']:.0f} кВт·ч")
        st.metric("Средняя дневная", f"{periods_data['avg_daily']:.1f} кВт·ч")
    
    with col3:
        st.metric("Средняя часовая", f"{periods_data['avg_hourly']:.2f} кВт·ч")
        daily_yield = periods_data['yearly_total'] / 365
        st.metric("Дневной yield", f"{daily_yield:.1f} кВт·ч/день")
    
    with col4:
        capacity_factor = (periods_data['yearly_total'] / (peak_power * 8760)) * 100
        st.metric("Коэффициент использования", f"{capacity_factor:.1f}%")
        specific_generation = periods_data['yearly_total'] / peak_power
        st.metric("Удельная генерация", f"{specific_generation:.0f} кВт·ч/кВт")
    
    # ===== ВКЛАДКИ ДЛЯ РАЗНЫХ ПЕРИОДОВ =====
    st.subheader("📈 Детальная аналитика по периодам")
    
    tab1, tab2, tab3, tab4 = st.tabs(["🏆 ГОДОВАЯ", "📅 МЕСЯЧНАЯ", "📆 НЕДЕЛЬНАЯ", "⏰ СУТОЧНАЯ"])
    
    with tab1:
        st.subheader("Годовая генерация")
        
        # График годовой генерации по месяцам
        fig_year, (ax1, ax2) = plt.subplots(1, 2, figsize=(15, 5))
        
        # График по месяцам
        months_ru = ["Янв", "Фев", "Мар", "Апр", "Май", "Июн", 
                    "Июл", "Авг", "Сен", "Окт", "Ноя", "Дек"]
        
        monthly_data = periods_data['monthly'].copy()
        monthly_data['month_name'] = [months_ru[i-1] for i in monthly_data['month']]
        
        bars = ax1.bar(monthly_data['month_name'], monthly_data['P'], 
                      color=plt.cm.viridis(np.linspace(0, 1, 12)),
                      alpha=0.7)
        
        ax1.set_title('Генерация по месяцам')
        ax1.set_ylabel('кВт·ч')
        ax1.grid(True, alpha=0.3)
        
        for bar in bars:
            height = bar.get_height()
            ax1.text(bar.get_x() + bar.get_width()/2., height + 5,
                    f'{height:.0f}', ha='center', va='bottom', fontsize=9)
        
        # Круговая диаграмма - распределение по сезонам
        seasons = {
            'Зима (Дек-Фев)': monthly_data[monthly_data['month'].isin([12, 1, 2])]['P'].sum(),
            'Весна (Мар-Май)': monthly_data[monthly_data['month'].isin([3, 4, 5])]['P'].sum(),
            'Лето (Июн-Авг)': monthly_data[monthly_data['month'].isin([6, 7, 8])]['P'].sum(),
            'Осень (Сен-Ноя)': monthly_data[monthly_data['month'].isin([9, 10, 11])]['P'].sum()
        }
        
        ax2.pie(seasons.values(), labels=seasons.keys(), autopct='%1.1f%%', 
                colors=['#ff9999', '#66b3ff', '#99ff99', '#ffcc99'])
        ax2.set_title('Распределение генерации по сезонам')
        
        plt.tight_layout()
        st.pyplot(fig_year)
        
        # Таблица годовых данных
        st.dataframe(monthly_data.rename(columns={'P': 'Генерация (кВт·ч)', 'month_name': 'Месяц'}), 
                    hide_index=True, use_container_width=True)
    
    with tab2:
        st.subheader("Месячная генерация")
        
        # Выбор месяца для детального анализа
        selected_month = st.selectbox("Выберите месяц:", months_ru, key="month_selector")
        month_num = months_ru.index(selected_month) + 1
        
        # Данные за выбранный месяц
        month_data = periods_data['raw_data'][periods_data['raw_data']['month'] == month_num]
        daily_month = month_data.groupby('date')['P'].sum().reset_index()
        daily_month['P'] = daily_month['P'] / 1000  # кВт·ч
        
        fig_month, (ax1, ax2) = plt.subplots(1, 2, figsize=(15, 5))
        
        # Дневная генерация в месяце
        ax1.plot(daily_month['date'], daily_month['P'], 'o-', linewidth=2, markersize=4)
        ax1.set_title(f'Дневная генерация - {selected_month}')
        ax1.set_ylabel('кВт·ч/день')
        ax1.grid(True, alpha=0.3)
        ax1.tick_params(axis='x', rotation=45)
        
        # Средняя часовая генерация по дням месяца
        hourly_avg = month_data.groupby('hour')['P'].mean().reset_index()
        hourly_avg['P'] = hourly_avg['P'] / 1000  # кВт·ч
        
        ax2.bar(hourly_avg['hour'], hourly_avg['P'], alpha=0.7, color='orange')
        ax2.set_title(f'Средняя часовая генерация - {selected_month}')
        ax2.set_xlabel('Час дня')
        ax2.set_ylabel('кВт·ч/час')
        ax2.grid(True, alpha=0.3)
        
        plt.tight_layout()
        st.pyplot(fig_month)
        
        st.metric(f"Общая генерация за {selected_month}", f"{daily_month['P'].sum():.0f} кВт·ч")
        st.metric(f"Средняя дневная генерация", f"{daily_month['P'].mean():.1f} кВт·ч")
    
    with tab3:
        st.subheader("Недельная генерация")
        
        fig_week, ax = plt.subplots(figsize=(12, 6))
        
        weekly_data = periods_data['weekly'].copy()
        
        ax.bar(weekly_data['week'], weekly_data['P'], alpha=0.7, color='green')
        ax.set_title('Недельная генерация в течение года')
        ax.set_xlabel('Номер недели')
        ax.set_ylabel('кВт·ч/неделю')
        ax.grid(True, alpha=0.3)
        
        # Добавляем линию тренда
        z = np.polyfit(weekly_data['week'], weekly_data['P'], 2)
        p = np.poly1d(z)
        ax.plot(weekly_data['week'], p(weekly_data['week']), "r--", alpha=0.8)
        
        plt.tight_layout()
        st.pyplot(fig_week)
        
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Максимальная неделя", f"{weekly_data['P'].max():.0f} кВт·ч")
        with col2:
            st.metric("Минимальная неделя", f"{weekly_data['P'].min():.0f} кВт·ч")
        with col3:
            st.metric("Стандартное отклонение", f"{weekly_data['P'].std():.0f} кВт·ч")
    
    with tab4:
        st.subheader("Суточная и почасовая генерация")
        
        # Выбор дня для детального анализа
        available_dates = periods_data['daily']['date'].unique()
        selected_date = st.selectbox("Выберите дату:", available_dates[:10])  # Показываем первые 10 дней
        
        # Данные за выбранный день
        day_data = periods_data['raw_data'][periods_data['raw_data']['date'] == selected_date]
        day_data['P_kwh'] = day_data['P'] / 1000  # кВт·ч
        
        fig_day, (ax1, ax2) = plt.subplots(1, 2, figsize=(15, 5))
        
        # Почасовая генерация
        ax1.bar(day_data['hour'], day_data['P_kwh'], alpha=0.7, color='red')
        ax1.set_title(f'Почасовая генерация - {selected_date}')
        ax1.set_xlabel('Час дня')
        ax1.set_ylabel('кВт·ч/час')
        ax1.grid(True, alpha=0.3)
        
        # Накопительная генерация за день
        cumulative = day_data['P_kwh'].cumsum()
        ax2.plot(day_data['hour'], cumulative, 'o-', linewidth=2, color='purple')
        ax2.set_title(f'Накопительная генерация - {selected_date}')
        ax2.set_xlabel('Час дня')
        ax2.set_ylabel('кВт·ч (накопит.)')
        ax2.grid(True, alpha=0.3)
        ax2.fill_between(day_data['hour'], cumulative, alpha=0.3, color='purple')
        
        plt.tight_layout()
        st.pyplot(fig_day)
        
        total_day = day_data['P_kwh'].sum()
        peak_hour = day_data.loc[day_data['P_kwh'].idxmax()]
        
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Общая дневная генерация", f"{total_day:.1f} кВт·ч")
        with col2:
            st.metric("Пиковый час", f"Час {int(peak_hour['hour'])}:00")
        with col3:
            st.metric("Пиковая мощность", f"{peak_hour['P_kwh']:.2f} кВт·ч")
    
    # ===== ТАБЛИЦА С ОСНОВНЫМИ ДАННЫМИ =====
    with st.expander("📋 Полная таблица данных"):
        display_df = periods_data['raw_data'].copy()
        display_df['P_kwh'] = display_df['P'] / 1000
        display_df = display_df[['time', 'date', 'hour', 'P_kwh']].rename(columns={
            'time': 'Время', 'date': 'Дата', 'hour': 'Час', 'P_kwh': 'Генерация (кВт·ч)'
        })
        st.dataframe(display_df.head(100), use_container_width=True)  # Показываем первые 100 строк

else:
    st.error("❌ Не удалось получить данные от PVGIS. Проверьте параметры и подключение к интернету.")

# ===== ФУТЕР =====
st.markdown("---")
st.markdown("*Данные предоставлены PVGIS API • Почасовые данные за 2020 год*")
