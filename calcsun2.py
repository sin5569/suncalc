import streamlit as st
import requests
import pandas as pd
import matplotlib.pyplot as plt
import folium
from streamlit_folium import st_folium, folium_static
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

# ===== ИНИЦИАЛИЗАЦИЯ СЕССИИ =====
if 'lat' not in st.session_state:
    st.session_state.lat = 49.5883  # Полтава
if 'lon' not in st.session_state:
    st.session_state.lon = 34.5514  # Полтава
if 'map_clicked' not in st.session_state:
    st.session_state.map_clicked = False

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

# Кнопка для выбора города
selected_city = st.sidebar.selectbox("Быстрый выбор города:", list(cities.keys()))
if st.sidebar.button("Применить выбранный город"):
    st.session_state.lat, st.session_state.lon = cities[selected_city]
    st.session_state.map_clicked = False
    st.rerun()

st.sidebar.markdown("---")
st.sidebar.write("**Или выберите на карте:**")
st.sidebar.info("🗺️ Нажмите на карту справа для выбора местоположения")

# Точная настройка координат
st.sidebar.write("**Текущие координаты:**")
col1, col2 = st.sidebar.columns(2)
with col1:
    lat = st.number_input("Широта", value=st.session_state.lat, format="%.6f", key="lat_input")
with col2:
    lon = st.number_input("Долгота", value=st.session_state.lon, format="%.6f", key="lon_input")

# Кнопка для применения ручного ввода координат
if st.sidebar.button("Применить координаты"):
    st.session_state.lat = lat
    st.session_state.lon = lon
    st.session_state.map_clicked = False
    st.rerun()

st.sidebar.markdown("---")

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
    "Оптимальный (широта)": round(st.session_state.lat),
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

# ===== ВЫБОР ГОДА ДАННЫХ =====
st.sidebar.header("📅 Параметры данных")

# Определяем доступные годы
available_years = list(range(2005, 2021))
selected_year = st.sidebar.selectbox(
    "Год данных для расчета:",
    options=available_years,
    index=available_years.index(2020)
)

if selected_year < 2015:
    st.sidebar.warning("⚠️ Используются относительно старые данные. Рекомендуется 2015-2020 годы.")

# ===== ИНТЕРАКТИВНАЯ КАРТА ДЛЯ ВЫБОРА МЕСТОПОЛОЖЕНИЯ =====
st.header("🗺️ Выбор местоположения на карте")

col_map, col_info = st.columns([2, 1])

with col_map:
    # Создаем карту для выбора местоположения
    m = folium.Map(
        location=[st.session_state.lat, st.session_state.lon], 
        zoom_start=10,
        control_scale=True
    )
    
    # Добавляем маркер текущего местоположения
    folium.Marker(
        [st.session_state.lat, st.session_state.lon],
        tooltip="Текущее местоположение",
        popup=f"Широта: {st.session_state.lat:.6f}<br>Долгота: {st.session_state.lon:.6f}",
        icon=folium.Icon(color="green", icon="ok-sign", prefix="fa")
    ).add_to(m)
    
    # Добавляем круг для лучшей видимости
    folium.CircleMarker(
        location=[st.session_state.lat, st.session_state.lon],
        radius=8,
        popup="Выбранная точка",
        color="#3186cc",
        fill=True,
        fill_color="#3186cc"
    ).add_to(m)
    
    # Инструкция для пользователя
    folium.Marker(
        [st.session_state.lat + 0.05, st.session_state.lon],
        icon=folium.DivIcon(
            html='<div style="font-size: 14px; color: black; background: white; padding: 5px; border-radius: 5px;">⬅️ Нажмите на карту для выбора нового местоположения</div>'
        )
    ).add_to(m)
    
    # Отображаем карту и получаем события
    map_data = st_folium(
        m, 
        width=700, 
        height=500,
        key="location_map"
    )
    
    # Обрабатываем клик по карте
    if map_data and map_data.get("last_clicked"):
        clicked_lat = map_data["last_clicked"]["lat"]
        clicked_lon = map_data["last_clicked"]["lng"]
        
        # Обновляем координаты в session state
        st.session_state.lat = clicked_lat
        st.session_state.lon = clicked_lon
        st.session_state.map_clicked = True
        
        # Обновляем числовые поля
        st.rerun()

with col_info:
    st.subheader("📍 Текущее местоположение")
    st.success(f"**Широта:** {st.session_state.lat:.6f}")
    st.success(f"**Долгота:** {st.session_state.lon:.6f}")
    
    # Определяем ближайший город
    min_distance = float('inf')
    nearest_city = "Не определен"
    
    for city, (city_lat, city_lon) in cities.items():
        distance = math.sqrt((st.session_state.lat - city_lat)**2 + (st.session_state.lon - city_lon)**2)
        if distance < min_distance:
            min_distance = distance
            nearest_city = city
    
    st.info(f"**Ближайший город:** {nearest_city}")
    
    # Кнопка для сброса к Полтаве
    if st.button("🔄 Сбросить к Полтаве"):
        st.session_state.lat = 49.5883
        st.session_state.lon = 34.5514
        st.session_state.map_clicked = False
        st.rerun()
    
    st.markdown("---")
    st.write("**Инструкция:**")
    st.write("1. Нажмите на карту слева для выбора местоположения")
    st.write("2. Или выберите город из списка в боковой панели")
    st.write("3. Или введите координаты вручную")

# ===== ИНДИКАТОР ЗАГРУЗКИ =====
st.header("⚡ Расчет солнечной генерации")

with st.spinner(f"Получение почасовых данных за {selected_year} год от PVGIS..."):
    data = get_pvgis_data(st.session_state.lat, st.session_state.lon, tilt, peak_power, azimuth, selected_year, selected_year)

# ===== ОБРАБОТКА ДАННЫХ =====
def parse_pvgis_hourly_data(data, selected_year):
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
    df['year'] = df['time'].dt.year
    
    # Рассчитываем генерацию энергии на основе солнечной радиации
    system_efficiency = 0.16  # 16% КПД системы
    panel_area = peak_power * 6.5  # м²
    
    # Генерация в Вт·ч за час и кВт·ч за час
    df['power_wh'] = df['G(i)'] * panel_area * system_efficiency
    df['power_kwh'] = df['power_wh'] / 1000
    
    return df

def calculate_periods_generation(df, peak_power):
    """Расчет генерации за разные периоды"""
    if df is None:
        return None
    
    # Почасовая генерация
    hourly = df.groupby(['date', 'hour']).agg({
        'power_kwh': 'sum',
        'G(i)': 'mean',
        'T2m': 'mean'
    }).reset_index()
    
    # Дневная генерация
    daily = df.groupby('date').agg({
        'power_kwh': 'sum',
        'G(i)': 'mean',
        'T2m': 'mean'
    }).reset_index()
    
    # Недельная генерация
    weekly = df.groupby('week').agg({
        'power_kwh': 'sum',
        'G(i)': 'mean',
        'T2m': 'mean'
    }).reset_index()
    
    # Месячная генерация
    monthly = df.groupby('month').agg({
        'power_kwh': 'sum',
        'G(i)': 'mean',
        'T2m': 'mean'
    }).reset_index()
    
    # Годовая генерация
    yearly_total = df['power_kwh'].sum()
    
    # Средние показатели
    avg_hourly = df['power_kwh'].mean()
    avg_daily = daily['power_kwh'].mean()
    avg_weekly = weekly['power_kwh'].mean()
    avg_monthly = monthly['power_kwh'].mean()
    
    # Статистика по радиации
    avg_radiation = df['G(i)'].mean()
    max_radiation = df['G(i)'].max()
    
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
        'avg_radiation': avg_radiation,
        'max_radiation': max_radiation,
        'raw_data': df,
        'data_year': df['year'].iloc[0] if len(df) > 0 else selected_year
    }

# Парсим данные
df_hourly = parse_pvgis_hourly_data(data, selected_year) if data else None

# Отладочная информация в сайдбаре
if df_hourly is not None:
    st.sidebar.success(f"✅ Данные за {selected_year} год успешно загружены")
    st.sidebar.write(f"📊 Записей: {len(df_hourly)} строк")
else:
    st.sidebar.error("❌ Не удалось загрузить данные")

periods_data = calculate_periods_generation(df_hourly, peak_power) if df_hourly is not None else None

# ===== ОТОБРАЖЕНИЕ РЕЗУЛЬТАТОВ =====
if periods_data is not None:
    # ===== КАРТА С НАПРАВЛЕНИЕМ ПАНЕЛЕЙ =====
    st.header("🎯 Ориентация солнечных панелей")
    
    # Создаем карту с направлением
    m_direction = folium.Map(
        location=[st.session_state.lat, st.session_state.lon], 
        zoom_start=15
    )
    
    # Расчет направления стрелки
    angle_rad = math.radians(azimuth)
    lat_offset = round(0.001 * math.cos(angle_rad), 6)
    lon_offset = round(0.001 * math.sin(angle_rad), 6)
    
    # Маркер установки
    folium.Marker(
        [st.session_state.lat, st.session_state.lon],
        tooltip=f"Установка: {direction}, {tilt}°",
        popup=f"""
        <b>Параметры системы:</b><br>
        Мощность: {peak_power} кВт<br>
        Направление: {direction}<br>
        Наклон: {tilt}°<br>
        Координаты: {st.session_state.lat:.6f}, {st.session_state.lon:.6f}<br>
        Год данных: {selected_year}
        """,
        icon=folium.Icon(color="blue", icon="screenshot", prefix="fa")
    ).add_to(m_direction)
    
    # Стрелка направления панелей
    folium.PolyLine(
        locations=[
            [st.session_state.lat, st.session_state.lon], 
            [st.session_state.lat + lat_offset, st.session_state.lon + lon_offset]
        ],
        color="red",
        weight=5,
        tooltip=f"Направление панелей: {direction}",
        opacity=0.8
    ).add_to(m_direction)
    
    # Добавляем компас
    folium.CircleMarker(
        location=[st.session_state.lat - 0.0005, st.session_state.lon],
        radius=3,
        popup="N - Север",
        color="black",
        fill=True
    ).add_to(m_direction)
    
    folium.Marker(
        [st.session_state.lat - 0.0005, st.session_state.lon],
        icon=folium.DivIcon(
            html='<div style="font-size: 12px; color: black; font-weight: bold;">N</div>'
        )
    ).add_to(m_direction)
    
    st_folium(m_direction, width=800, height=400)
    
    # ===== СВОДКА ПОКАЗАТЕЛЕЙ =====
    st.header("📊 Сводка генерации")
    
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
    st.header("📈 Детальная аналитика")
    
    tab1, tab2, tab3, tab4 = st.tabs(["🏆 ГОДОВАЯ", "📅 МЕСЯЧНАЯ", "📆 НЕДЕЛЬНАЯ", "⏰ СУТОЧНАЯ"])
    
    with tab1:
        st.subheader(f"Годовая генерация - {selected_year} год")
        
        fig_year, (ax1, ax2) = plt.subplots(1, 2, figsize=(15, 5))
        
        months_ru = ["Янв", "Фев", "Мар", "Апр", "Май", "Июн", 
                    "Июл", "Авг", "Сен", "Окт", "Ноя", "Дек"]
        
        monthly_data = periods_data['monthly'].copy()
        monthly_data['month_name'] = [months_ru[i-1] for i in monthly_data['month']]
        
        bars = ax1.bar(monthly_data['month_name'], monthly_data['power_kwh'], 
                      color=plt.cm.viridis(np.linspace(0, 1, 12)),
                      alpha=0.7)
        
        ax1.set_title(f'Генерация по месяцам - {selected_year} год')
        ax1.set_ylabel('кВт·ч')
        ax1.grid(True, alpha=0.3)
        plt.xticks(rotation=45)
        
        for bar in bars:
            height = bar.get_height()
            ax1.text(bar.get_x() + bar.get_width()/2., height + 5,
                    f'{height:.0f}', ha='center', va='bottom', fontsize=9)
        
        # Круговая диаграмма
        seasons = {
            'Зима (Дек-Фев)': monthly_data[monthly_data['month'].isin([12, 1, 2])]['power_kwh'].sum(),
            'Весна (Мар-Май)': monthly_data[monthly_data['month'].isin([3, 4, 5])]['power_kwh'].sum(),
            'Лето (Июн-Авг)': monthly_data[monthly_data['month'].isin([6, 7, 8])]['power_kwh'].sum(),
            'Осень (Сен-Ноя)': monthly_data[monthly_data['month'].isin([9, 10, 11])]['power_kwh'].sum()
        }
        
        ax2.pie(seasons.values(), labels=seasons.keys(), autopct='%1.1f%%', 
                colors=['#ff9999', '#66b3ff', '#99ff99', '#ffcc99'])
        ax2.set_title(f'Распределение по сезонам - {selected_year} год')
        
        plt.tight_layout()
        st.pyplot(fig_year)
        
    # Остальные вкладки остаются без изменений...
    # [Код для остальных вкладок остается таким же как в предыдущей версии]

else:
    st.error("❌ Не удалось получить данные от PVGIS. Проверьте параметры и подключение к интернету.")

# ===== ФУТЕР =====
st.markdown("---")
st.markdown(f"*Данные предоставлены PVGIS API • Местоположение: {st.session_state.lat:.6f}, {st.session_state.lon:.6f} • Год данных: {selected_year}*")
