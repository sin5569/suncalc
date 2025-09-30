import streamlit as st
import requests
import pandas as pd
import matplotlib.pyplot as plt
import folium
from streamlit_folium import st_folium
import math

st.set_page_config(layout="wide")
st.title("☀️ Калькулятор солнечной генерации с картой и ориентацией")

# ===== Ввод координат с высокой точностью =====
st.sidebar.header("📍 Локация и ориентация панелей")
lat = st.sidebar.number_input("Широта", value=50.450000, format="%.6f")
lon = st.sidebar.number_input("Долгота", value=30.523333, format="%.6f")

# Стороны света (8 направлений)
directions = {
    "Север": 0,
    "Северо-Восток": 45,
    "Восток": 90,
    "Юго-Восток": 135,
    "Юг": 180,
    "Юго-Запад": 225,
    "Запад": 270,
    "Северо-Запад": 315
}
direction = st.sidebar.radio("Ориентация панели:", list(directions.keys()))
azimuth = directions[direction]  # угол направления панели для PVGIS

# ===== Параметры панели =====
st.header("⚡ Параметры панели")
peak_power = st.number_input("Установленная мощность системы (кВт)", value=5.0)
tilt = st.slider("Угол наклона панели (°)", 0, 90, 30)

# ===== Запрос данных PVGIS с учетом направления панели =====
@st.cache_data(show_spinner=True)
def get_pvgis_data(lat, lon, tilt, peak_power, azimuth):
    url = (
        f"https://re.jrc.ec.europa.eu/api/PVcalc?"
        f"lat={lat}&lon={lon}&peakpower={peak_power}&loss=14&angle={tilt}&azimuth={azimuth}&outputformat=json"
    )
    response = requests.get(url)
    if response.status_code == 200:
        return response.json()
    return None

data = get_pvgis_data(lat, lon, tilt, peak_power, azimuth)

def parse_pvgis_data(data):
    if not data or "outputs" not in data:
        return None
    monthly = data["outputs"]["monthly"]["fixed"]
    df = pd.DataFrame(monthly)
    df["month"] = [
        "Янв","Фев","Мар","Апр","Май","Июн",
        "Июл","Авг","Сен","Окт","Ноя","Дек"
    ]
    return df[["month","E_m","H(i)_m","SD_m"]]

df = parse_pvgis_data(data)

# ===== Вывод таблицы и графика =====
if df is not None:
    st.subheader("📊 Солнечная генерация по месяцам")
    st.dataframe(df)

    fig, ax = plt.subplots()
    ax.bar(df["month"], df["E_m"], color="orange")
    ax.set_ylabel("Выработка (кВт·ч/мес)")
    ax.set_title("Солнечная генерация с учётом ориентации и наклона")
    st.pyplot(fig)

    total = df["E_m"].sum()
    st.success(f"🌞 Общая генерация за год: **{total:.1f} кВт·ч**")
else:
    st.error("Не удалось получить данные от PVGIS")

# ===== Карта с маркером и стрелкой направления =====
st.subheader("🗺️ Местоположение и направление панели")

angle_deg = azimuth
angle_rad = math.radians(angle_deg)

# смещение стрелки (~100 м), с точностью до 6 знаков
lat_offset = round(0.001 * math.cos(angle_rad), 6)
lon_offset = round(0.001 * math.sin(angle_rad), 6)

# создаём карту
m = folium.Map(location=[lat, lon], zoom_start=15)

# точка установки
folium.Marker(
    [lat, lon],
    tooltip="Место установки",
    icon=folium.Icon(color="blue", icon="home")
).add_to(m)

# стрелка направления панели
folium.PolyLine(
    locations=[[lat, lon], [lat + lat_offset, lon + lon_offset]],
    color="red",
    weight=5,
    tooltip=f"Направление: {direction}"
).add_to(m)

st_folium(m, width=700, height=500)
