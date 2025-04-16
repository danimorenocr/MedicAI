import pandas as pd
import streamlit as st
import plotly.express as px
import snowflake.connector
from dotenv import load_dotenv
import os
from datetime import datetime


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
    
    # Convertir las columnas de tipo timestamp a string para evitar errores con PyArrow
    for col in df.columns:
        if df[col].dtype == 'object':  # Columnas que pueden contener timestamps
            df[col] = df[col].apply(lambda x: x.strftime('%Y-%m-%d %H:%M:%S') if isinstance(x, (pd.Timestamp, datetime)) else x)
    
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
           diagnosis_provided, session_duration_seconds, satisfaction_status,
           user_feedback, user_rating, confirmation_status, messages_exchanged
    FROM bot_interactions
    WHERE interaction_start BETWEEN '2025-01-01' AND '2025-12-31';
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
        fig = px.bar(data['DIAGNOSIS_PROVIDED'].value_counts().head(10),
                     color_discrete_sequence=['#E0115F'])
        st.plotly_chart(fig, use_container_width=True)
    st.markdown("</div>", unsafe_allow_html=True)


with col2:
    st.markdown("<div class='card metric-container'>", unsafe_allow_html=True)
    st.metric("Total de Interacciones", len(data))
    st.markdown("</div>", unsafe_allow_html=True)
    
    if 'SESSION_DURATION_SECONDS' in data.columns:
        avg_session_duration = pd.to_numeric(data['SESSION_DURATION_SECONDS'], errors='coerce').mean()
        st.markdown("<div class='card metric-container'>", unsafe_allow_html=True)
        st.metric("Duración Promedio de la Sesión (segundos)", round(avg_session_duration, 2))
        st.markdown("</div>", unsafe_allow_html=True)
    
    if 'USER_RATING' in data.columns:
        # Convertir a numérico y calcular promedio (ignorando valores no convertibles)
        ratings = pd.to_numeric(data['USER_RATING'], errors='coerce')
        avg_rating = ratings.mean()
        st.markdown("<div class='card metric-container'>", unsafe_allow_html=True)
        st.metric("Calificación Promedio (1-5 ⭐)", round(avg_rating, 2))
        st.markdown("</div>", unsafe_allow_html=True)

# Visualización de síntomas reportados
st.markdown("<div class='card'>", unsafe_allow_html=True)
st.header("\U0001F9A0 Análisis de Síntomas Reportados")
if 'SYMPTOMS_REPORTED' in data.columns:
    fig = px.bar(data['SYMPTOMS_REPORTED'].value_counts().head(10),
                 color_discrete_sequence=['#E0115F'])
    st.plotly_chart(fig, use_container_width=True)
st.markdown("</div>", unsafe_allow_html=True)

# Feedback y satisfacción
st.markdown("<div class='card'>", unsafe_allow_html=True)
st.header("\U0001F44D Análisis de Satisfacción de Usuarios")
col_feedback1, col_feedback2 = st.columns(2)

with col_feedback1:
    if 'SATISFACTION_STATUS' in data.columns:
        satisfaction_counts = data['SATISFACTION_STATUS'].value_counts().reset_index()
        satisfaction_counts.columns = ['Estado', 'Cantidad']
        fig = px.pie(satisfaction_counts, values='Cantidad', names='Estado', 
                   title='Distribución de Satisfacción',
                   color_discrete_sequence=px.colors.sequential.Reds)
        st.plotly_chart(fig, use_container_width=True)

with col_feedback2:
    if 'USER_RATING' in data.columns:
        # Asegurar que USER_RATING sea numérico para la gráfica
        rating_counts = pd.to_numeric(data['USER_RATING'], errors='coerce').value_counts().sort_index().reset_index()
        rating_counts.columns = ['Calificación', 'Cantidad']
        fig = px.bar(rating_counts, x='Calificación', y='Cantidad',
                    title='Distribución de Calificaciones',
                    color_discrete_sequence=['#E0115F'])
        fig.update_layout(xaxis_title='Calificación (Estrellas)', yaxis_title='Número de usuarios')
        st.plotly_chart(fig, use_container_width=True)
st.markdown("</div>", unsafe_allow_html=True)

# Analítica de Mensajes y Confirmación
st.markdown("<div class='card'>", unsafe_allow_html=True)
st.header("\U0001F4AC Análisis de Interacción")
col_interact1, col_interact2 = st.columns(2)

with col_interact1:
    if 'MESSAGES_EXCHANGED' in data.columns:
        # Convertir a numérico para cálculos
        data['MESSAGES_EXCHANGED'] = pd.to_numeric(data['MESSAGES_EXCHANGED'], errors='coerce')
        fig = px.histogram(data, x='MESSAGES_EXCHANGED',
                         title='Distribución de Mensajes por Sesión',
                         color_discrete_sequence=['#E0115F'])
        fig.update_layout(xaxis_title='Número de Mensajes', yaxis_title='Frecuencia')
        st.plotly_chart(fig, use_container_width=True)

with col_interact2:
    if 'CONFIRMATION_STATUS' in data.columns:
        confirm_counts = data['CONFIRMATION_STATUS'].value_counts().reset_index()
        confirm_counts.columns = ['Estado', 'Cantidad']
        fig = px.pie(confirm_counts, values='Cantidad', names='Estado', 
                   title='Confirmación de Síntomas',
                   color_discrete_sequence=px.colors.sequential.Reds)
        st.plotly_chart(fig, use_container_width=True)
st.markdown("</div>", unsafe_allow_html=True)

# Frecuencia de usuarios
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
try:
    min_date = pd.to_datetime('2025-01-01')
    max_date = pd.to_datetime('2025-12-31')
    interaction_date = st.date_input("Selecciona la fecha de la interacción", 
                                   min_value=min_date, 
                                   max_value=max_date)

    if interaction_date:
        query_date = f"""
        SELECT user_id, interaction_start, interaction_end, symptoms_reported, 
               diagnosis_provided, session_duration_seconds, satisfaction_status,
               user_feedback, user_rating
        FROM bot_interactions
        WHERE interaction_start::DATE = '{interaction_date}';
        """
        filtered_data = fetch_data_from_snowflake(query_date)
        if not filtered_data.empty:
            st.dataframe(filtered_data)
        else:
            st.info("No hay datos para la fecha seleccionada.")
except Exception as e:
    st.error(f"Error al filtrar por fecha: {e}")
st.markdown("</div>", unsafe_allow_html=True)