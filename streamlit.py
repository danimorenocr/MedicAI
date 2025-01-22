import pandas as pd 
import streamlit as st
from datetime import datetime
import snowflake.connector

def fetch_data_from_snowflake(query):
    conn = snowflake.connector.connect(
        user='DANIMORENOCR',
        password='@DANIjuli0110',
        account='wbkzjad-meb03147',
        warehouse='chatbot_wh',
        database='prueba',
        schema='PUBLIC'
    )
    cursor = conn.cursor()
    cursor.execute(query)
    data = cursor.fetchall()
    columns = [desc[0] for desc in cursor.description]
    df = pd.DataFrame(data, columns=columns)
    cursor.close()
    conn.close()
    return df

# Configurar título
st.title("Análisis de Interacciones del Chatbot")

# Consultar datos
query = "SELECT * FROM bot_interactions;"
data = fetch_data_from_snowflake(query)

# Mostrar los datos en una tabla
st.header("Datos Recuperados")
st.dataframe(data)

# Análisis básico
st.header("Análisis Básico")

# 1. Contar el total de interacciones
total_interactions = len(data)
st.metric("Total de Interacciones", total_interactions)

# 2. Diagnósticos proporcionados
diagnostics_count = data['DIAGNOSIS_PROVIDED'].value_counts()
st.subheader("Diagnósticos Proporcionados")
st.bar_chart(diagnostics_count)

# 3. Tiempos promedio de interacción
if 'SESSION_DURATION_SECONDS' in data.columns:
    avg_session_duration = data['SESSION_DURATION_SECONDS'].mean()
    st.metric("Duración Promedio de las Sesiones (segundos)", round(avg_session_duration, 2))

# 4. Filtro de fecha
st.header("Filtrar por Fecha")
date_filter = st.date_input("Selecciona una fecha", datetime.now().date())
filtered_data = data[pd.to_datetime(data['INTERACTION_START']).dt.date == date_filter]
st.dataframe(filtered_data)

# 5. Análisis de satisfacción
if 'SATISFACTION_STATUS' in data.columns:
    satisfaction_counts = data['SATISFACTION_STATUS'].value_counts()
    st.subheader("Estado de Satisfacción")
    st.bar_chart(satisfaction_counts)

# 6. Análisis de síntomas reportados
st.header("Análisis de Síntomas Reportados")
symptoms_count = data['SYMPTOMS_REPORTED'].value_counts().head(10)  # top 10 síntomas
st.bar_chart(symptoms_count)

# 7. Tiempo promedio de respuesta
if 'SESSION_DURATION_SECONDS' in data.columns:
    # Validar que no haya valores negativos en SESSION_DURATION_SECONDS
    invalid_durations = data[data['SESSION_DURATION_SECONDS'] < 0]
    valid_durations = data[data['SESSION_DURATION_SECONDS'] >= 0]
    
    # Mostrar advertencia si se encuentran valores negativos
    if not invalid_durations.empty:
        st.warning(f"Se encontraron {len(invalid_durations)} registros con duraciones negativas en 'SESSION_DURATION_SECONDS'. Estos serán excluidos del cálculo.")
    
    # Calcular el tiempo promedio de respuesta
    avg_session_duration = valid_durations['SESSION_DURATION_SECONDS'].mean()
    st.metric("Tiempo Promedio de Respuesta (segundos)", round(avg_session_duration, 2))
else:
    st.error("La columna 'SESSION_DURATION_SECONDS' no está disponible en los datos.")

# 8. Análisis de interacciones con errores
st.header("Análisis de Interacciones con Errores")
error_interactions = data[data['ERROR_DETAILS'].notna()]
st.metric("Interacciones con Errores", len(error_interactions))
st.dataframe(error_interactions[['INTERACTION_ID', 'ERROR_DETAILS']])

# 9. Análisis de la actividad de usuarios (Inactividad)
st.header("Análisis de Inactividad de Usuarios")
inactive_users = data[data['INACTIVITY_FLAG'] == 1]
st.metric("Interacciones con Inactividad", len(inactive_users))

# 10. Frecuencia de interacciones por usuario
st.header("Frecuencia de Interacciones por Usuario")
user_interactions = data['USER_ID'].value_counts()
st.bar_chart(user_interactions.head(10))  # top 10 usuarios con más interacciones

# 11. Análisis de diagnósticos proporcionados según el tiempo de la sesión
st.header("Diagnósticos Proporcionados por Duración de la Sesión")
data['session_duration_minutes'] = data['SESSION_DURATION_SECONDS'] / 60
diagnosis_by_duration = data.groupby('session_duration_minutes')['DIAGNOSIS_PROVIDED'].value_counts().unstack()
st.bar_chart(diagnosis_by_duration)

# 12. Relación entre el diagnóstico y la satisfacción
st.header("Relación entre Diagnóstico y Satisfacción")
diagnosis_satisfaction = data.groupby(['DIAGNOSIS_PROVIDED', 'SATISFACTION_STATUS']).size().unstack()
st.bar_chart(diagnosis_satisfaction)

# 13. Análisis de los mensajes intercambiados
st.header("Análisis de Mensajes Intercambiados")
messages_count = data['MESSAGES_EXCHANGED'].value_counts().head(10)
st.bar_chart(messages_count)

# 14. Análisis de interacciones según el estado de confirmación
st.header("Análisis de Confirmación de Estado")
confirmation_status_count = data['CONFIRMATION_STATUS'].value_counts()
st.bar_chart(confirmation_status_count)

