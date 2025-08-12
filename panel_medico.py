import os
from supabase import create_client, Client
import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime
from dotenv import load_dotenv
import matplotlib.pyplot as plt
from wordcloud import WordCloud

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
if not SUPABASE_URL or not SUPABASE_KEY:
    st.error("Falta SUPABASE_URL o SUPABASE_KEY en .env")
    st.stop()

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

st.set_page_config(page_title="Medic AI — Panel Médico", layout="wide")
st.title("📊 Medic AI — Panel Médico")

# ---------- Helpers ----------
@st.cache_data(ttl=60)
def load_sesiones():
    res = supabase.table("sesiones").select("*").order("fecha_inicio", desc=True).execute()
    return pd.DataFrame(res.data) if res.data else pd.DataFrame()

@st.cache_data(ttl=60)
def load_consultas():
    res = supabase.table("consultas").select("*").order("fecha", desc=True).execute()
    return pd.DataFrame(res.data) if res.data else pd.DataFrame()

def to_datetime_col(df, col):
    if col in df.columns and not df[col].isnull().all():
        df[col] = pd.to_datetime(df[col])
    return df

def update_consulta_flag(consulta_id, error_flag: bool, comentario: str):
    supabase.table("consultas").update({
        "error_detectado": error_flag,
        "comentario_analisis": comentario
    }).eq("id", consulta_id).execute()

def refresh_cache():
    load_sesiones.clear()
    load_consultas.clear()

# ---------- Load data ----------
with st.spinner("Cargando datos desde Supabase..."):
    sesiones_df = load_sesiones()
    consultas_df = load_consultas()

sesiones_df = to_datetime_col(sesiones_df, "fecha_inicio")
sesiones_df = to_datetime_col(sesiones_df, "fecha_fin")
consultas_df = to_datetime_col(consultas_df, "fecha")

# ---------- Sidebar filtros ----------
st.sidebar.header("Filtros")
min_date = sesiones_df["fecha_inicio"].min().date() if not sesiones_df.empty else None
max_date = sesiones_df["fecha_inicio"].max().date() if not sesiones_df.empty else None

date_from = st.sidebar.date_input("Desde", min_value=min_date, value=min_date) if min_date else None
date_to = st.sidebar.date_input("Hasta", min_value=min_date, value=max_date) if max_date else None

usuario_filter = st.sidebar.text_input("Filtrar por chat_id (Usuario) — deja vacío = todos")
estado_filter = st.sidebar.selectbox("Estado", ["Todos"] + (sesiones_df["estado"].dropna().unique().tolist() if not sesiones_df.empty else []))
satisfaccion_filter = st.sidebar.selectbox("Satisfacción", ["Todos", "Sí", "No"])
min_rating = st.sidebar.slider("Calificación mínima", 0, 5, 0)

apply_filters = st.sidebar.button("Aplicar filtros")

# ---------- Aplicar filtros ----------
df = sesiones_df.copy()
if not df.empty:
    if date_from and date_to:
        df = df[(df["fecha_inicio"].dt.date >= date_from) & (df["fecha_inicio"].dt.date <= date_to)]
    if usuario_filter:
        # buscar por chat_id (usuario_id campo guarda FK numérico — si guardas chat_id en usuarios, necesitarás JOIN)
        # asumimos que usuario_filter puede ser chat_id o usuario_id; intentar int
        try:
            v = int(usuario_filter)
            df = df[df["usuario_id"] == v]
        except:
            pass
    if estado_filter and estado_filter != "Todos":
        df = df[df["estado"] == estado_filter]
    if satisfaccion_filter != "Todos":
        val = True if satisfaccion_filter == "Sí" else False
        if "satisfaccion" in df.columns:
            df = df[df["satisfaccion"] == val]
    if "calificacion" in df.columns:
        df = df[df["calificacion"].fillna(0) >= min_rating]

# ---------- Layout principal ----------
left_col, right_col = st.columns((2, 1))

with left_col:
    st.subheader("📋 Sesiones")
    st.write("Número de sesiones mostradas:", len(df))
    st.dataframe(df.reset_index(drop=True), use_container_width=True)

    # Export CSV
    if not df.empty:
        csv = df.to_csv(index=False).encode("utf-8")
        st.download_button("📥 Exportar sesiones CSV", data=csv, file_name="sesiones_medicaid.csv", mime="text/csv")

    # Estadísticas rápidas
    if not df.empty:
        st.subheader("📈 Estadísticas")
        col1, col2, col3 = st.columns(3)
        col1.metric("Total sesiones", len(df))
        if "satisfaccion" in df.columns:
            sat_pct = round(df["satisfaccion"].dropna().mean() * 100, 2)
            col2.metric("Satisfacción (%)", f"{sat_pct}%")
        else:
            col2.metric("Satisfacción (%)", "N/A")
        if "calificacion" in df.columns:
            col3.metric("Calificación promedio", round(df["calificacion"].dropna().mean(), 2))
        else:
            col3.metric("Calificación promedio", "N/A")

        # Sesiones por día
        if "fecha_inicio" in df.columns:
            sesiones_por_dia = df.groupby(df["fecha_inicio"].dt.date).size().reset_index(name="count")
            fig1 = px.bar(sesiones_por_dia, x="fecha_inicio", y="count", title="Sesiones por día")
            st.plotly_chart(fig1, use_container_width=True)

        # Distribución de calificaciones
        if "calificacion" in df.columns and not df["calificacion"].isnull().all():
            fig2 = px.histogram(df, x="calificacion", nbins=5, title="Distribución de calificaciones")
            st.plotly_chart(fig2, use_container_width=True)

with right_col:
    st.subheader("🔎 Buscar sesión / analizar")
    sesion_id_selected = st.selectbox("Seleccionar sesión (id)", options=(df["id"].tolist() if not df.empty else []))
    if sesion_id_selected:
        st.markdown("### Detalle de la sesión")
        s = sesiones_df[sesiones_df["id"] == sesion_id_selected].squeeze()
        st.write(s.to_dict())

        # Mostrar consultas asociadas
        consultas_s = consultas_df[consultas_df["sesion_id"] == sesion_id_selected].sort_values("fecha")
        st.markdown("#### Consultas (historial de la sesión)")
        if consultas_s.empty:
            st.info("No hay consultas guardadas para esta sesión.")
        else:
            # Mostrar tabla simple
            st.dataframe(consultas_s[["id","tipo_mensaje","pregunta","respuesta_usuario","respuesta_bot","error_detectado","comentario_analisis","fecha"]].reset_index(drop=True))

            # Panel de revisión: permitir marcar errores / comentar
            st.markdown("#### Panel de revisión (actualizar consulta)")
            consulta_id = st.selectbox("Seleccionar consulta (id) para marcar/revisar", options=consultas_s["id"].tolist())
            if consulta_id:
                fila = consultas_s[consultas_s["id"] == consulta_id].squeeze()
                st.write("**Consulta seleccionada:**")
                st.write(fila.to_dict())

                col_a, col_b = st.columns(2)
                with col_a:
                    error_flag = st.checkbox("Marcar como error_detectado", value=bool(fila.get("error_detectado", False)))
                with col_b:
                    comentario = st.text_area("Comentario de análisis", value=fila.get("comentario_analisis", "") or "", height=120)

                if st.button("💾 Guardar análisis (consulta)"):
                    update_consulta_flag(consulta_id, error_flag, comentario)
                    st.success("Guardado. Actualiza la página para ver cambios.")
                    refresh_cache()

# ---------- Panel de diagnósticos y métricas ----------
st.markdown("---")
st.subheader("🔬 Diagnósticos y calidad")
# Extraer diagnósticos
diagnosticos = consultas_df[consultas_df["tipo_mensaje"] == "diagnostico"].copy()
if not diagnosticos.empty:
    diagnosticos["fecha"] = pd.to_datetime(diagnosticos["fecha"])
    diag_by_day = diagnosticos.groupby(diagnosticos["fecha"].dt.date).size().reset_index(name="count")
    fig_diag = px.line(diag_by_day, x="fecha", y="count", title="Diagnósticos por día")
    st.plotly_chart(fig_diag, use_container_width=True)

    # Errores detectados
    errores = diagnosticos[diagnosticos["error_detectado"] == True]
    st.write(f"Diagnósticos marcados como error_detectado: {len(errores)}")
    if not errores.empty:
        st.dataframe(errores[["id","sesion_id","respuesta_bot","comentario_analisis","fecha"]].reset_index(drop=True))
else:
    st.info("No hay diagnósticos registrados aún.")

# ---------- Export completo consultas ----------
st.markdown("---")
if not consultas_df.empty:
    csv_cons = consultas_df.to_csv(index=False).encode("utf-8")
    st.download_button("📥 Exportar consultas CSV", data=csv_cons, file_name="consultas_medicaid.csv", mime="text/csv")



# 📊 --- Análisis de Preguntas ---
st.subheader("📊 Análisis de Preguntas (13 tipos)")

# Obtener datos de consultas
data_consultas = supabase.table("consultas").select("*").execute()
df_consultas = pd.DataFrame(data_consultas.data)

# Filtrar solo preguntas de síntomas
tipos_preguntas = [f"pregunta_sintomas_{i}" for i in range(1, 13)] + ["confirmacion_sintomas"]
df_preg = df_consultas[df_consultas["tipo_mensaje"].isin(tipos_preguntas)].copy()

if df_preg.empty:
    st.warning("No hay registros de las 13 preguntas para analizar.")
else:
    # Conteo y porcentaje
    conteo = df_preg.groupby("tipo_mensaje").size().reset_index(name="cantidad")
    conteo["porcentaje"] = (conteo["cantidad"] / conteo["cantidad"].sum()) * 100

    # Longitud promedio
    df_preg["longitud_respuesta"] = df_preg["respuesta_usuario"].astype(str).apply(len)
    longitudes = df_preg.groupby("tipo_mensaje")["longitud_respuesta"].mean().reset_index()

    # Merge
    resumen = conteo.merge(longitudes, on="tipo_mensaje")
    resumen = resumen.sort_values(by="cantidad", ascending=False)

    # Mostrar resumen
    st.dataframe(resumen)

    # 📊 Gráfico de barras
    fig, ax = plt.subplots()
    ax.bar(resumen["tipo_mensaje"], resumen["cantidad"], color="skyblue")
    ax.set_xticklabels(resumen["tipo_mensaje"], rotation=45, ha="right")
    ax.set_ylabel("Cantidad de respuestas")
    ax.set_title("Cantidad de respuestas por tipo de pregunta")
    st.pyplot(fig)

    # ⚠️ Respuestas vacías
    vacias = df_preg[df_preg["respuesta_usuario"].isnull() | (df_preg["respuesta_usuario"] == "")]
    if not vacias.empty:
        st.markdown("### ⚠️ Respuestas vacías")
        st.dataframe(vacias[["sesion_id", "tipo_mensaje"]])

    # ❌ Errores detectados
    errores = df_preg[df_preg["error_detectado"] == True]
    if not errores.empty:
        st.markdown("### ❌ Preguntas con errores detectados")
        st.dataframe(errores[["sesion_id", "tipo_mensaje", "comentario_analisis"]])

    # ☁️ Word cloud general
    texto_total = " ".join(df_preg["respuesta_usuario"].dropna().astype(str))
    if texto_total.strip():
        st.markdown("### ☁️ Nube de palabras (todas las preguntas)")
        wc = WordCloud(width=800, height=400, background_color="white").generate(texto_total)
        fig_wc, ax_wc = plt.subplots(figsize=(10, 5))
        ax_wc.imshow(wc, interpolation="bilinear")
        ax_wc.axis("off")
        st.pyplot(fig_wc)