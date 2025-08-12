import pandas as pd
import streamlit as st

# ============================
# 1. Cargar datos
# ============================
df = pd.read_json("consultas.json")  # tu archivo

# Filtrar solo las preguntas de síntomas
df_preg = df[df["tipo_mensaje"] == "pregunta_sintomas"].copy()

# ============================
# 2. Lista oficial de las 13 preguntas
# ============================
preguntas_clave = [
    "Descripción de los síntomas",
    "Duración de los síntomas",
    "Intensidad de los síntomas",
    "Frecuencia de los síntomas",
    "Cambios en los síntomas",
    "Datos relevantes adicionales",
    "Antecedentes médicos",
    "Enfermedades crónicas",
    "Alergias",
    "Edad",
    "Sexo",
    "Peso",
    "Altura"
]

# ============================
# 3. Clasificación de respuestas
# ============================
def clasificar_respuesta(texto):
    if not texto or pd.isna(texto):
        return "Vacía"
    texto = str(texto).strip().lower()
    if len(texto) < 5:
        return "Muy corta"
    elif len(texto) > 100:
        return "Detallada"
    else:
        return "Normal"

df_preg["clasificacion"] = df_preg["respuesta_usuario"].apply(clasificar_respuesta)

# ============================
# 4. Organización por sesión
# ============================
# Creamos un diccionario {sesion_id: {pregunta: (respuesta, clasificacion)}}
sesiones_dict = {}
for sesion_id, grupo in df_preg.groupby("sesion_id"):
    grupo_ordenado = grupo.reset_index(drop=True)
    preguntas_sesion = {}
    for idx, pregunta in enumerate(preguntas_clave):
        if idx < len(grupo_ordenado):
            respuesta = grupo_ordenado.loc[idx, "respuesta_usuario"]
            clasif = grupo_ordenado.loc[idx, "clasificacion"]
        else:
            respuesta = None
            clasif = "No respondida"
        preguntas_sesion[pregunta] = {
            "respuesta": respuesta,
            "clasificacion": clasif
        }
    sesiones_dict[sesion_id] = preguntas_sesion

# ============================
# 5. Mostrar en Streamlit
# ============================
st.title("📋 Análisis de Sesiones Médicas")
sesion_sel = st.selectbox("Seleccionar sesión", list(sesiones_dict.keys()))

st.subheader(f"🩺 Preguntas y respuestas - Sesión {sesion_sel}")
for pregunta, datos in sesiones_dict[sesion_sel].items():
    st.markdown(f"**{pregunta}**")
    st.write(f"Respuesta: {datos['respuesta']}")
    st.write(f"Clasificación: `{datos['clasificacion']}`")
    st.markdown("---")
