import streamlit as st
import pandas as pd
import folium
import geopandas as gpd
from streamlit_folium import st_folium
from folium.plugins import HeatMap
import seaborn as sns
import matplotlib.pyplot as plt
import gspread
from google.oauth2.service_account import Credentials
import numpy as np
import time

# ================================
# 🔹 CONFIG GLOBAL
# ================================
SHEET_ID = "1mRJ8L9coZ8Uq49RIlgL9uZffSBBW_k2kSpYW4E6Wrgg"

def format_chile(valor):
    return f"{valor:,.0f}".replace(',', '.')

st.set_page_config(
    page_title="Dashboard Grupo de Defensa - Diego Vásquez",
    layout="wide"
)

# ================================
# 🔹 CONEXIÓN GOOGLE SHEETS
# ================================
def get_gsheet_client(scope):
    creds = Credentials.from_service_account_info(
        st.secrets["gcp_service_account"],
        scopes=scope
    )
    return gspread.authorize(creds)

# ================================
# 🔹 AUTO REFRESH (cada 30 seg)
# ================================
if "last_refresh" not in st.session_state:
    st.session_state.last_refresh = time.time()

if time.time() - st.session_state.last_refresh > 30:
    st.session_state.last_refresh = time.time()
    st.cache_data.clear()
    st.rerun()

# ================================
# 🔹 CARGA DESDE GOOGLE SHEETS
# ================================
@st.cache_data(ttl=30, show_spinner="🔄 Sincronizando datos con Google Sheets...")
def load_data_from_gsheet(sheet_id):
    scope = ["https://www.googleapis.com/auth/spreadsheets.readonly"]
    client = get_gsheet_client(scope)

    sheet = client.open_by_key(sheet_id)
    worksheet = sheet.get_worksheet(0)

    data = worksheet.get_all_values()

    headers = data[0]
    rows = data[1:]

    df = pd.DataFrame(rows, columns=headers)

    # 🔥 LIMPIEZA
    cols = ['venta_neta', 'lat', 'lng', 'kms_dist', 'lat_cd', 'lng_cd', 'unidades']

    for col in cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce')

    if 'fecha_compra' in df.columns:
        df['fecha_compra'] = pd.to_datetime(df['fecha_compra'], errors='coerce', dayfirst=True)

    df = df.dropna(subset=['lat', 'lng'])

    if 'comuna' in df.columns:
        df['comuna'] = df['comuna'].str.upper().str.strip()

    return df

# ================================
# 🔹 GUARDAR EN GOOGLE SHEETS
# ================================
def save_to_gsheet(df, sheet_id):
    scope = ["https://www.googleapis.com/auth/spreadsheets"]
    client = get_gsheet_client(scope)

    sheet = client.open_by_key(sheet_id)
    worksheet = sheet.get_worksheet(0)

    df_clean = df.copy()

    # Fechas → string
    for col in df_clean.select_dtypes(include=['datetime64[ns]']).columns:
        df_clean[col] = df_clean[col].dt.strftime('%Y-%m-%d %H:%M:%S')

    # NaN / inf
    df_clean = df_clean.replace([np.inf, -np.inf], np.nan)
    df_clean = df_clean.fillna("")

    df_clean = df_clean.astype(object)

    worksheet.clear()
    worksheet.update(
        [df_clean.columns.tolist()] + df_clean.values.tolist()
    )

# ================================
# 🔹 GEOJSON
# ================================
@st.cache_data
def load_geojson():
    geo = gpd.read_file("comunas_metropolitana-1.geojson")
    geo['name'] = geo['name'].str.upper().str.strip()
    return geo

# ================================
# 🔹 BOTÓN SINCRONIZACIÓN MANUAL
# ================================
st.sidebar.markdown("### 🔄 Sincronización")

 

# Mostrar última actualización
if "last_refresh" in st.session_state:
    st.sidebar.caption(
        f"Última actualización: {time.strftime('%H:%M:%S', time.localtime(st.session_state.last_refresh))}"
    )

# ================================
# 🔹 CARGA DATA
# ================================
try:
    df = load_data_from_gsheet(SHEET_ID)
    geo_data = load_geojson()
except Exception as e:
    st.error(f"Error al cargar datos: {e}")
    st.stop()

# ================================
# 🔹 FILTROS
# ================================
st.sidebar.header("Filtros")

canal_selected = st.sidebar.multiselect(
    "Canal de Venta",
    options=sorted(df['canal'].unique()),
    default=df['canal'].unique()
)

cd_selected = st.sidebar.multiselect(
    "Centro de Distribución",
    options=sorted(df['centro_dist'].unique()),
    default=df['centro_dist'].unique()
)

comuna_selected = st.sidebar.multiselect(
    "Comuna",
    options=sorted(df['comuna'].unique()),
    default=df['comuna'].unique()
)

min_v = int(df['venta_neta'].min())
max_v = int(df['venta_neta'].max())

rango_venta = st.sidebar.slider(
    "Venta Neta",
    min_v, max_v, (min_v, max_v)
)

fecha_min = df['fecha_compra'].min().date()
fecha_max = df['fecha_compra'].max().date()

fecha_rango = st.sidebar.date_input(
    "Periodo",
    (fecha_min, fecha_max)
)

mask = (
    (df['canal'].isin(canal_selected)) &
    (df['centro_dist'].isin(cd_selected)) &
    (df['comuna'].isin(comuna_selected)) &
    (df['venta_neta'] >= rango_venta[0]) &
    (df['venta_neta'] <= rango_venta[1])
)

if isinstance(fecha_rango, tuple):
    mask = mask & (
        df['fecha_compra'].dt.date.between(fecha_rango[0], fecha_rango[1])
    )

df_filtered = df[mask]

# ================================
# 🔹 KPIs
# ================================
st.title("Dashboard Grupo de Defensa")

if not df_filtered.empty:
    total = len(df_filtered)
    venta = df_filtered['venta_neta'].sum()

    k1, k2, k3 = st.columns(3)

    k1.metric("Venta Total", f"$ {format_chile(venta)}")
    k2.metric("Pedidos", total)
    k3.metric("Ticket Promedio", f"$ {format_chile(df_filtered['venta_neta'].mean())}")

# ================================
# 🔹 TABS
# ================================
tab1, tab2, tab3 = st.tabs([
    "Mapa",
    "Estadística",
    "Gestión"
])

# ================================
# 🔹 MAPA
# ================================
with tab1:
    m = folium.Map(location=[-33.45, -70.65], zoom_start=11)
    data = df_filtered[['lat', 'lng']].dropna().values.tolist()
    HeatMap(data).add_to(m)
    st_folium(m, width=1000, height=500)

# ================================
# 🔹 ESTADÍSTICAS
# ================================
with tab2:
    if not df_filtered.empty:
        fig, ax = plt.subplots()
        sns.histplot(df_filtered['venta_neta'], ax=ax)
        st.pyplot(fig)

# ================================
# 🔹 CRUD
# ================================
with tab3:
    edited_df = st.data_editor(df, use_container_width=True)

    col1, col2 = st.columns([2,1])

    # 💾 GUARDAR
    with col1:
        if st.button("💾 Guardar cambios"):
            save_to_gsheet(edited_df, SHEET_ID)
            st.cache_data.clear()
            st.success("Guardado en Google Sheets")
            st.rerun()

    # 🔄 SINCRONIZAR
    with col2:
        if st.button("🔄 Sincronizar ahora"):
            st.cache_data.clear()
            st.session_state.last_refresh = time.time()
            st.success("Datos actualizados desde Google Sheets")
            st.rerun()