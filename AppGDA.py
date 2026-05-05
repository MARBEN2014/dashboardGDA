import streamlit as st
import pandas as pd
import folium
import geopandas as gpd
from streamlit_folium import st_folium
from folium.plugins import HeatMap, MarkerCluster
import seaborn as sns
import matplotlib.pyplot as plt
import matplotlib.ticker as mtick
import gspread
from google.oauth2.service_account import Credentials

def format_chile(valor):
   
    return f"{valor:,.0f}".replace(',', '.')

# Configuración de página
st.set_page_config(page_title="Dashboard Grupo de Defensa - Diego Vásquez", layout="wide")

# Carga de datos
@st.cache_data
def load_data():
    nombre_archivo = "dataset_tarea_ind.xlsx"
    df = pd.read_excel(nombre_archivo, engine='openpyxl')
    
  
    cols_a_limpiar = ['venta_neta', 'lat', 'lng', 'kms_dist', 'lat_cd', 'lng_cd', 'unidades']
    for col in cols_a_limpiar:
        if col in df.columns:
            df[col] = df[col].astype(str).str.replace(',', '.').astype(float)
    
    
    df['fecha_compra'] = pd.to_datetime(df['fecha_compra'], dayfirst=True)
    
     
    df = df.dropna(subset=['lat', 'lng'])
    
    
    df['comuna'] = df['comuna'].str.upper().str.strip()
    return df





@st.cache_data
def load_geojson():
    geo = gpd.read_file("comunas_metropolitana-1.geojson")
    geo['name'] = geo['name'].str.upper().str.strip()
    return geo

 
try:
    df = load_data()
    geo_data = load_geojson()
except Exception as e:
    st.error(f"Error al cargar archivos: {e}")
    st.stop()

# Filtros 
st.sidebar.header(" Filtros")

 
if st.sidebar.button("🔄 Resetear Filtros"):
    st.rerun()



 
canal_selected = st.sidebar.multiselect(
    "Canal de Venta:",
    options=sorted(df['canal'].unique()),
    default=df['canal'].unique()
)

 
cd_selected = st.sidebar.multiselect(
    "Centro de Distribución (CD):",
    options=sorted(df['centro_dist'].unique()),
    default=df['centro_dist'].unique()
)

 
comuna_selected = st.sidebar.multiselect(
    "Comunas de Entrega:",
    options=sorted(df['comuna'].unique()),
    default=df['comuna'].unique()
)

 
min_v = int(df['venta_neta'].min())
max_v = int(df['venta_neta'].max())
rango_venta = st.sidebar.slider("Valor de Venta Neta ($):", min_v, max_v, (min_v, max_v))

 
fecha_min_data = df['fecha_compra'].min().date()
fecha_max_data = df['fecha_compra'].max().date()

st.sidebar.subheader("Periodo de Análisis")
fecha_rango = st.sidebar.date_input(
    "Seleccione el periodo:",
    value=(fecha_min_data, fecha_max_data),
    min_value=fecha_min_data,
    max_value=fecha_max_data
)

 
mask = (
    (df['canal'].isin(canal_selected)) &
    (df['centro_dist'].isin(cd_selected)) &
    (df['comuna'].isin(comuna_selected)) &
    (df['venta_neta'] >= rango_venta[0]) &
    (df['venta_neta'] <= rango_venta[1])
)

 
if isinstance(fecha_rango, tuple) and len(fecha_rango) == 2:
    mask = mask & (df['fecha_compra'].dt.date >= fecha_rango[0]) & (df['fecha_compra'].dt.date <= fecha_rango[1])

df_filtered = df[mask]

#  CUERPO  
st.title(" Dashboard de Visualización de Grupo De Defensa")
st.markdown(f"**Alumno:** Diego Vásquez Orellana")

 
if not df_filtered.empty:
  
    total_p = len(df_filtered)
    pedidos_app = len(df_filtered[df_filtered['canal'].str.upper() == 'APP'])
    pedidos_sitio = len(df_filtered[df_filtered['canal'].str.upper() == 'SITIO'])
    
    pct_app = (pedidos_app / total_p) * 100 if total_p > 0 else 0
    pct_sitio = (pedidos_sitio / total_p) * 100 if total_p > 0 else 0

    
    k1, k2, k3 = st.columns(3)
    
    with k1:
         
        st.metric("Venta Total Filtrada", f"$ {format_chile(df_filtered['venta_neta'].sum())}")
        
    with k2:
        
        st.metric("Total Pedidos", format_chile(total_p))
        
        
        st.markdown(f"""
            <div style="display: inline-block; padding: 5px 12px; margin-top: -10px; 
                        background-color: #f0f2f6; border-radius: 8px; border: 1px solid #d1d5db;white-space: nowrap;">
                <span style="color: #0000FF; font-size: 18px; font-weight: 900;">📱 App: {pct_app:.1f}%</span>
                <span style="color: #333; font-size: 18px; font-weight: bold; margin: 0 8px;">|</span>
                <span style="color: #006400; font-size: 18px; font-weight: 900;">💻 Sitio: {pct_sitio:.1f}%</span>
            </div>
            """, unsafe_allow_html=True)
        
    with k3:
        
        st.metric("Ticket Promedio", f"$ {format_chile(df_filtered['venta_neta'].mean())}")
        
     

else:
    st.warning(" No hay datos para los filtros seleccionados.")


tab1, tab2, tab3 = st.tabs([
    " Visualización Geoespacial",
    " Análisis Estadístico",
    "✏️ Gestión de Datos"
])


def save_to_gsheet(df, sheet_url):
    scope = ["https://www.googleapis.com/auth/spreadsheets"]

    creds = Credentials.from_service_account_info(
        st.secrets["gcp_service_account"],
        scopes=scope
    )

    client = gspread.authorize(creds)

    # 🔥 usamos ID limpio (más robusto)
    sheet_id = sheet_url.split("/d/")[1].split("/")[0]

    sheet = client.open_by_key(sheet_id)
    worksheet = sheet.get_worksheet(0)

    worksheet.clear()

    worksheet.update([df.columns.values.tolist()] + df.values.tolist())

with tab1:
    st.subheader("Explorador Geográfico")
    tipo_mapa = st.selectbox(
        "Seleccione Capa de Análisis:",
        ["1.- Mapa Red Logística (CDs y Entregas)", 
         "2.- Mapa de Calor: Densidad de Pedidos", 
         "3.- Mapa de Calor: Intensidad Económica (Ventas)", 
         "4.- Mapa Coropleta: Venta Neta por Comuna",
         "5.- Análisis Combinado: Ventas + Densidad" ]
    )
    
    m = folium.Map(location=[-33.45694, -70.64827], zoom_start=11,min_zoom=10,
    max_zoom=16, tiles='cartodbpositron')

    if not df_filtered.empty:

        if tipo_mapa == "1.- Mapa Red Logística (CDs y Entregas)":

     
            cds_unicos = df_filtered.drop_duplicates(subset=['centro_dist'])
            for _, row in cds_unicos.iterrows():
                folium.Marker(
                    location=[row['lat_cd'], row['lng_cd']],
                    popup=f"<b>CD:</b> {row['centro_dist']}<br><b>Comuna:</b> {row['comuna']}",
                    tooltip=row['centro_dist'],
                    icon=folium.Icon(color='red', icon='home', prefix='fa')
                ).add_to(m)

            
            muestra = df_filtered.sample(n=min(1000, len(df_filtered)), random_state=42)
            
            marker_cluster = MarkerCluster(name="Entregas a Clientes").add_to(m)

            for _, row in muestra.iterrows():
                folium.CircleMarker(
                    location=[row['lat'], row['lng']],
                    radius=3,
                    color='blue',
                    fill=True,
                    fill_color='blue',
                    fill_opacity=0.6,
                    popup=f"<b>Venta:</b> ${row['venta_neta']:.0f}<br><b>Canal:</b> {row['canal']}"
                ).add_to(marker_cluster)
                
            st_folium(m, width="100%", height=600)
            
        elif tipo_mapa == "2.- Mapa de Calor: Densidad de Pedidos":

            
            m = folium.Map(
                location=[-33.45694, -70.64827],
                zoom_start=11,
                min_zoom=10,
                max_zoom=16,
                tiles='cartodbpositron'
            )

            
            data_cantidad = df_filtered[['lat', 'lng']].dropna().values.tolist()

            HeatMap(
                data_cantidad,
                radius=12,
                blur=8,
                min_opacity=0.4,
                gradient={0.4: 'blue', 0.65: 'lime', 1: 'red'}
            ).add_to(m)
            
            geo_data['name'] = geo_data['name'].str.upper().str.strip()

            folium.GeoJson(
                geo_data,
                style_function=lambda x: {
                    'fillColor': 'transparent',
                    'color': 'gray',
                    'weight': 1
                },
                highlight_function=lambda x: {
                    'fillColor': 'yellow',
                    'color': 'black',
                    'weight': 2,
                    'fillOpacity': 0.4
                },
                tooltip=folium.GeoJsonTooltip(
                    fields=['name'],
                    aliases=['Comuna:']
                )
            ).add_to(m)
        
            cds_unicos = df_filtered.drop_duplicates(subset=['centro_dist'])

            for _, row in cds_unicos.iterrows():
                folium.Marker(
                    location=[row['lat_cd'], row['lng_cd']],
                    popup=f"<b>CD:</b> {row['centro_dist']}<br><b>Comuna:</b> {row['comuna']}",
                    tooltip=row['centro_dist'],
                    icon=folium.Icon(color='black', icon='home', prefix='fa')
                ).add_to(m)
            st_folium(m, width="100%", height=600)
    
        elif tipo_mapa == "3.- Mapa de Calor: Intensidad Económica (Ventas)":

            
            m = folium.Map(
                location=[-33.45694, -70.64827],
                zoom_start=11,
                min_zoom=10,
                max_zoom=16,
                tiles='cartodbpositron'
            )
            max_val = df_filtered['venta_neta'].max()
            max_val = max_val if max_val > 0 else 1

            df_filtered = df_filtered.copy()   
            df_filtered['venta_norm'] = df_filtered['venta_neta'] / max_val

            
            data_venta = df_filtered[['lat', 'lng', 'venta_norm']].dropna().values.tolist()

            HeatMap(
                data_venta,
                radius=15,
                blur=10,
                min_opacity=0.5
            ).add_to(m)
            cds_unicos = df_filtered.drop_duplicates(subset=['centro_dist'])

            for _, row in cds_unicos.iterrows():
                folium.Marker(
                    location=[row['lat_cd'], row['lng_cd']],
                    popup=f"<b>CD:</b> {row['centro_dist']}<br><b>Comuna:</b> {row['comuna']}",
                    tooltip=row['centro_dist'],
                    icon=folium.Icon(color='black', icon='home', prefix='fa')
                ).add_to(m)
            geo_data['name'] = geo_data['name'].str.upper().str.strip()

            folium.GeoJson(
                geo_data,
                style_function=lambda x: {
                    'fillColor': 'transparent',
                    'color': 'gray',
                    'weight': 1
                },
                highlight_function=lambda x: {
                    'fillColor': 'yellow',
                    'color': 'black',
                    'weight': 2,
                    'fillOpacity': 0.4
                },
                tooltip=folium.GeoJsonTooltip(
                    fields=['name'],
                    aliases=['Comuna:']
                )
            ).add_to(m)
            st_folium(m, width="100%", height=600)
    
        elif tipo_mapa == "4.- Mapa Coropleta: Venta Neta por Comuna":

            
            m = folium.Map(
                location=[-33.45694, -70.64827],
                zoom_start=10,
                min_zoom=10,
                max_zoom=16,
                tiles='cartodbpositron'
            )
            
            ventas_comuna = df_filtered.groupby('comuna')['venta_neta'].sum().reset_index()
            ventas_comuna['comuna'] = ventas_comuna['comuna'].str.upper().str.strip()

            
            geo_data['name'] = geo_data['name'].str.upper().str.strip()

             
            choropleth = folium.Choropleth(
                geo_data=geo_data,
                name="choropleth",
                data=ventas_comuna,
                columns=["comuna", "venta_neta"],
                key_on="feature.properties.name",
                fill_color="YlGnBu",
                fill_opacity=0.7,
                line_opacity=0.2,
                legend_name="Venta Neta Total por Comuna ($)",
                highlight=True,
                bins=3  
            ).add_to(m)
            cds_unicos = df_filtered.drop_duplicates(subset=['centro_dist'])

            for _, row in cds_unicos.iterrows():
                folium.Marker(
                    location=[row['lat_cd'], row['lng_cd']],
                    popup=f"<b>CD:</b> {row['centro_dist']}<br><b>Comuna:</b> {row['comuna']}",
                    tooltip=row['centro_dist'],
                    icon=folium.Icon(color='red', icon='home', prefix='fa')
                ).add_to(m)
            ventas_dict = ventas_comuna.set_index('comuna')['venta_neta'].to_dict()

            for feature in choropleth.geojson.data['features']:
                nom_comuna = feature['properties']['name']
                venta = ventas_dict.get(nom_comuna, 0)
                feature['properties']['Venta_Total_Fmt'] = f"$ {venta:,.0f}"

            choropleth.geojson.add_child(
                folium.features.GeoJsonTooltip(
                    fields=['name', 'Venta_Total_Fmt'],
                    aliases=['Comuna:', 'Ventas Totales:'],
                    localize=True
                )
            )

             
            st_folium(m, width="100%", height=600)

        elif tipo_mapa == "5.- Análisis Combinado: Ventas + Densidad":

            
            m = folium.Map(
                location=[-33.45694, -70.64827],
                zoom_start=11,
                min_zoom=10,
                max_zoom=16,
                tiles='cartodbpositron'
            )           
            ventas_comuna = df_filtered.groupby('comuna')['venta_neta'].sum().reset_index()
            ventas_comuna['comuna'] = ventas_comuna['comuna'].str.upper().str.strip()
            ventas_comuna['venta_mm'] = ventas_comuna['venta_neta'] / 1_000_000

            geo_data['name'] = geo_data['name'].str.upper().str.strip()

           
            choropleth = folium.Choropleth(
                geo_data=geo_data,
                data=ventas_comuna,
                columns=["comuna", "venta_mm"],
                key_on="feature.properties.name",
                fill_color="YlGn",
                fill_opacity=0.4,
                line_opacity=0.2,
                legend_name="Venta Neta por Comuna (MM$)",
                highlight=True
            ).add_to(m)

            
            cds_unicos = df_filtered.drop_duplicates(subset=['centro_dist'])

            for _, row in cds_unicos.iterrows():
                folium.Marker(
                    location=[row['lat_cd'], row['lng_cd']],
                    popup=f"<b>CD:</b> {row['centro_dist']}<br><b>Comuna:</b> {row['comuna']}",
                    tooltip=row['centro_dist'],
                    icon=folium.Icon(color='red', icon='home', prefix='fa')   
                ).add_to(m)

            
            ventas_dict = ventas_comuna.set_index('comuna')['venta_neta'].to_dict()

            for feature in choropleth.geojson.data['features']:
                nom = feature['properties']['name']
                venta = ventas_dict.get(nom, 0)
                feature['properties']['info_tooltip'] = f"Comuna: {nom} | Ventas: $ {venta:,.0f}"

            choropleth.geojson.add_child(
                folium.features.GeoJsonTooltip(
                    fields=['info_tooltip'],
                    labels=False,
                    sticky=True
                )
            )

            data_puntos = df_filtered[['lat', 'lng']].dropna().values.tolist()

            HeatMap(
                data_puntos,
                radius=12,
                blur=18,
                min_opacity=0.3,
                gradient={0.4: 'blue', 0.6: 'purple', 1: 'red'},
                name="Densidad de Pedidos (Calor)"  
            ).add_to(m)

            
            folium.LayerControl().add_to(m)

          
            st_folium(m, width="100%", height=600, returned_objects=[])

with tab2:
    if not df_filtered.empty:
        c1, c2 = st.columns(2)
        with c1:
            st.write("#### Distribución por Canal")
            canal_counts = df_filtered['canal'].value_counts()
            fig1, ax1 = plt.subplots()
            ax1.pie(canal_counts, labels=canal_counts.index, autopct='%1.1f%%', colors=sns.color_palette('viridis', len(canal_counts)))
            ax1.add_artist(plt.Circle((0,0), 0.4, fc='white'))
            st.pyplot(fig1)

        with c2:
            st.write("#### Ventas por Centro de Distribución")
            cd_sales = df_filtered.groupby('centro_dist')['venta_neta'].sum().sort_values(ascending=False)
            fig2, ax2 = plt.subplots()
            sns.barplot(x=cd_sales.values, y=cd_sales.index, palette='viridis', hue=cd_sales.index, legend=False, ax=ax2)
            ax2.xaxis.set_major_formatter(mtick.FuncFormatter(lambda x, _: f'{x/1e6:.1f}M'))
            st.pyplot(fig2)

        st.write("#### Evolución Temporal de Unidades")
        temporal = df_filtered.groupby('fecha_compra')['unidades'].sum().reset_index()
        fig3, ax3 = plt.subplots(figsize=(12, 4))
        sns.lineplot(data=temporal, x='fecha_compra', y='unidades', marker='o', color='#21918c', ax=ax3)
        plt.xticks(rotation=45)
        st.pyplot(fig3)
    else:
        st.info("Utilice los filtros laterales para visualizar el análisis estadístico.")
        
with tab3:
    st.subheader("✏️ Edición de Datos (CRUD básico)")

    # Editor interactivo
    edited_df = st.data_editor(
        df,
        use_container_width=True,
        num_rows="dynamic"  # permite agregar/eliminar filas
    )

    # Detectar cambios
    if not edited_df.equals(df):
        st.warning("⚠️ Hay cambios sin guardar")

    col1, col2 = st.columns(2)

    # 💾 GUARDAR
    with col1:
        if st.button("💾 Guardar cambios"):
    
            # 🔹 Guarda local (opcional)
            edited_df.to_excel("dataset_tarea_ind.xlsx", index=False)

            # 🔹 Guarda en Google Sheets
            save_to_gsheet(
                edited_df,
                "https://docs.google.com/spreadsheets/d/1OmWufDYx3kAhU0A4Ovn8HmWhvB7kBIROQaHVj97wKpU"
            )

            st.cache_data.clear()
            st.success("✅ Datos guardados en Google Sheets")
            st.rerun()

    # 🗑️ RESET
    with col2:
        if st.button("🔄 Descartar cambios"):
            st.rerun()
            





st.divider()

st.markdown("### Análisis e Insights de la Visualización de Datos")

st.markdown("""
<div style="text-align: justify;">

El análisis geoespacial mediante Folium permitió incorporar el contexto territorial en la interpretación de los datos, facilitando la identificación de patrones de concentración de la demanda y su relación con los centros de distribución. Este enfoque complementa el análisis tradicional, entregando una visión más integral para la toma de decisiones.

Asimismo, la construcción del mapa de coropletas evidenció desafíos tanto técnicos como interpretativos, principalmente asociados a la normalización de datos geográficos y a posibles sesgos visuales derivados del tamaño de las comunas.

En términos de implementación, la integración con Streamlit destacó la importancia de optimizar el rendimiento mediante el uso de caching, control de latencia y técnicas de muestreo, asegurando una experiencia de usuario fluida.

</div>
""", unsafe_allow_html=True)


st.markdown("""
**Insights Clave**

- **Visión territorial de la demanda:**  
  Identificación de clústeres y patrones espaciales que no son visibles en gráficos tradicionales.

- **Desafíos en visualización geográfica:**  
  Requiere precisión en datos y una interpretación cuidadosa para evitar sesgos.

- **Rendimiento del dashboard:**  
  Uso eficiente de `st.cache_data` y muestreo para garantizar fluidez.

- **Oportunidades estratégicas:**  
  Optimización de última milla, fortalecimiento del canal digital y mejor distribución de carga entre centros.

""")