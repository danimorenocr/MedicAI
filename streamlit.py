import pandas as pd
import streamlit as st
import plotly.express as px
import snowflake.connector
from dotenv import load_dotenv
import os


load_dotenv()  # Carga las variables del archivo .env

def fetch_data_from_snowflake(query):
    conn = snowflake.connector.connect(
        user=os.getenv('SNOWFLAKE_USER'),
        password=os.getenv('SNOWFLAKE_PASSWORD'),
        account=os.getenv('SNOWFLAKE_ACCOUNT'),
        warehouse=os.getenv('SNOWFLAKE_WAREHOUSE'),
        database=os.getenv('SNOWFLAKE_DATABASE'),
        schema=os.getenv('SNOWFLAKE_SCHEMA')
    )
    cursor = conn.cursor()
    cursor.execute(query)
    data = cursor.fetchall()
    columns = [desc[0] for desc in cursor.description]
    df = pd.DataFrame(data, columns=columns)
    cursor.close()
    conn.close()
    return df

# Función para truncar cadenas largas
def truncate_columns(df, max_length=30):
    for col in df.columns:
        if df[col].dtype == 'object':  # Solo truncamos columnas de texto
            df[col] = df[col].apply(lambda x: x[:max_length] if isinstance(x, str) else x)
    return df

st.set_page_config(layout="wide")
st.markdown(""" 
    <style>
        body {
            background-color: #121212;
            color: white;
        }
        .card {
            background: #1e1e1e;
            padding: 20px;
            border-radius: 12px;
            box-shadow: 4px 4px 12px rgba(255, 0, 0, 0.2);
            margin-bottom: 20px;
        }
        .metric-container {
            display: flex;
            justify-content: space-around;
        }
    </style>
""", unsafe_allow_html=True)

st.title("\U0001F916 Análisis de Interacciones del Chatbot")

# Filtrar por un rango de fechas
query = """
    SELECT user_id, interaction_start, interaction_end, symptoms_reported, 
           diagnosis_provided, session_duration_seconds 
    FROM bot_interactions
    WHERE interaction_start BETWEEN '2025-01-01' AND '2025-01-31';
"""

data = fetch_data_from_snowflake(query)

# Reemplazar valores nulos con 'N/R'
data = data.fillna("N/R")

# Truncar las columnas que tienen texto
data = truncate_columns(data, max_length=30)

col1, col2 = st.columns([2, 1])

with col1:
    st.markdown("<div class='card'>", unsafe_allow_html=True)
    st.header("\U0001F4C8 Datos Recuperados")
    st.dataframe(data)
    st.markdown("</div>", unsafe_allow_html=True)

    st.markdown("<div class='card'>", unsafe_allow_html=True)
    st.header("\U0001F5C3 Diagnósticos Proporcionados")
    if 'DIAGNOSIS_PROVIDED' in data.columns:
        fig = px.bar(data['DIAGNOSIS_PROVIDED'].value_counts(),
                     color_discrete_sequence=['#E0115F'])
        st.plotly_chart(fig, use_container_width=True)
    st.markdown("</div>", unsafe_allow_html=True)


with col2:
    st.markdown("<div class='card metric-container'>", unsafe_allow_html=True)
    st.metric("Total de Interacciones", len(data))
    st.markdown("</div>", unsafe_allow_html=True)
    
    if 'SESSION_DURATION_SECONDS' in data.columns:
        avg_session_duration = data['SESSION_DURATION_SECONDS'].mean()
        st.markdown("<div class='card metric-container'>", unsafe_allow_html=True)
        st.metric("Duración Promedio de la Sesión (segundos)", round(avg_session_duration, 2))
        st.markdown("</div>", unsafe_allow_html=True)

st.markdown("<div class='card'>", unsafe_allow_html=True)
st.header("\U0001F9A0 Análisis de Síntomas Reportados")
if 'SYMPTOMS_REPORTED' in data.columns:
    fig = px.bar(data['SYMPTOMS_REPORTED'].value_counts().head(10),
                 color_discrete_sequence=['#E0115F'])
    st.plotly_chart(fig, use_container_width=True)
st.markdown("</div>", unsafe_allow_html=True)

st.markdown("<div class='card'>", unsafe_allow_html=True)
st.header("\U0001F464 Frecuencia de Interacciones por Usuario")
if 'USER_ID' in data.columns:
    fig = px.bar(data['USER_ID'].value_counts().head(10),
                 color_discrete_sequence=['#E0115F'])
    st.plotly_chart(fig, use_container_width=True)
st.markdown("</div>", unsafe_allow_html=True)

# Filtro por fecha de interacción
st.markdown("<div class='card'>", unsafe_allow_html=True)
st.header("\U0001F4C5 Buscar Interacción por Fecha")

# Selector de fecha
interaction_date = st.date_input("Selecciona la fecha de la interacción", min_value=pd.to_datetime('2025-01-01'), max_value=pd.to_datetime('2025-01-31'))

if interaction_date:
    query_date = f"""
    SELECT user_id, interaction_start, interaction_end, symptoms_reported, 
           diagnosis_provided, session_duration_seconds 
    FROM bot_interactions
    WHERE interaction_start::DATE = '{interaction_date}';
    """
    filtered_data = fetch_data_from_snowflake(query_date)
    st.dataframe(filtered_data)
st.markdown("</div>", unsafe_allow_html=True)