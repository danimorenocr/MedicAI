import streamlit as st
from supabase import create_client, Client
from dotenv import load_dotenv
import os

# ============================
# 1. Cargar variables del .env
# ============================
load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

st.set_page_config(page_title="Análisis de Sesiones Médicas", layout="wide")

if not SUPABASE_URL or not SUPABASE_KEY:
    st.error("⚠️ No se encontraron SUPABASE_URL y SUPABASE_KEY en el archivo .env")
else:
    supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

    # ============================
    # 2. Funciones para cargar datos
    # ============================
    def obtener_usuarios():
        response = supabase.table("usuarios").select("*").execute()
        return response.data if response.data else []

    def obtener_sesiones(usuario_id: int):
        response = supabase.table("sesiones").select("*").eq("usuario_id", usuario_id).execute()
        return response.data if response.data else []

    def obtener_consultas(sesion_id: int):
        response = supabase.table("consultas").select("*").eq("sesion_id", sesion_id).execute()
        return response.data if response.data else []

    # ============================
    # 3. Interfaz en Streamlit
    # ============================
    st.title("📋 Análisis de Sesiones Médicas")

    # Dividir la pantalla en 2 columnas
    col1, col2 = st.columns([2, 1])

    # Inicializar para evitar referencias antes de asignación
    usuario_id = None

    # ============================
    # Panel derecho: búsqueda de usuario
    # ============================
    with col2:
        st.subheader("👤 Buscar paciente")

        usuarios = obtener_usuarios()

        if usuarios:
            buscador = st.text_input("Buscar paciente por nombre o ID")

            usuarios_filtrados = [
                u for u in usuarios
                if (buscador.lower() in u.get('nombre', '').lower()) or (buscador in str(u.get('id', '')))
            ]

            if usuarios_filtrados:
                seleccion = st.radio(
                    "Seleccionar paciente",
                    [f"{u.get('nombre','(sin nombre)')} (ID {u.get('id','?')})" for u in usuarios_filtrados]
                )

                usuario_id = next(
                    u.get('id') for u in usuarios_filtrados
                    if f"{u.get('nombre','(sin nombre)')} (ID {u.get('id','?')})" == seleccion
                )
                usuario_info = next(u for u in usuarios if u.get("id") == usuario_id)

                # Obtener campos de forma segura con .get()
                id_chat = usuario_info.get('id de chat', 'No disponible')   # O 'id_chat' según tu schema
                fecha_registro = usuario_info.get('fecha_registro', 'No disponible')

                # Mostrar datos estéticos
                st.markdown("### 📑 Datos del usuario")
                st.markdown(f"""
                <div style='background-color: #f9f9f9; padding: 12px; border-radius: 10px; border: 1px solid #e5e7eb;'>
                  <div style='font-weight:600; margin-bottom:6px;'>{usuario_info.get('nombre', 'No disponible')}</div>
                  <div><strong>ID:</strong> {usuario_info.get('id', 'No disponible')}</div>
                  <div><strong>ID de Chat:</strong> {id_chat}</div>
                  <div><strong>Fecha de registro:</strong> {fecha_registro}</div>
                </div>
                """, unsafe_allow_html=True)
            else:
                st.warning("No se encontraron pacientes con ese término.")
        else:
            st.warning("⚠️ No hay usuarios en Supabase.")

    # ============================
    # Panel izquierdo: sesiones y consultas
    # ============================
    with col1:
        if usuario_id:
            st.subheader(f"🩺 Sesiones del usuario ID {usuario_id}")

            sesiones = obtener_sesiones(usuario_id)

            if sesiones:
                sesion_sel = st.selectbox("Seleccionar sesión", [s.get("id") for s in sesiones])

                sesion_info = next(s for s in sesiones if s.get("id") == sesion_sel)

                # Obtener valores de forma segura
                estado = sesion_info.get('estado', 'Desconocido')
                fecha_inicio = sesion_info.get('fecha_inicio', 'No registrada')
                fecha_fin = sesion_info.get('fecha_fin')

                # Mostrar sesión de manera estética
                st.markdown("### 🕑 Información de la sesión")
                st.markdown(f"""
                <div style='background-color: #eef6ff; padding: 12px; border-radius: 10px; border: 1px solid #c7d2fe;'>
                  <div><strong>Estado:</strong> {estado}</div>
                  <div><strong>Fecha inicio:</strong> {fecha_inicio}</div>
                  <div><strong>Fecha fin:</strong> {fecha_fin if fecha_fin else "En curso"}</div>
                </div>
                """, unsafe_allow_html=True)

                # ----- Consultas -----
                consultas = obtener_consultas(sesion_sel)
                if consultas:
                    st.markdown("### 📌 Consultas de la sesión")

                    # Guardaremos "respuesta_bot" y "comentario_analisis" para mostrarlos al final
                    resumen_final = []

                    for c in consultas:
                        st.markdown(f"**{c.get('tipo_mensaje', 'Sin tipo')}**")
                        st.write(f"Pregunta: {c.get('pregunta', 'No disponible')}")
                        st.write(f"Respuesta usuario: {c.get('respuesta_usuario', 'No disponible')}")

                        # Acumular para el resumen final (no mostrar aquí)
                        resumen_final.append({
                            "tipo": c.get('tipo_mensaje', 'Sin tipo'),
                            "respuesta_bot": c.get('respuesta_bot', 'No disponible'),
                            "comentario_analisis": c.get('comentario_analisis', 'No disponible')
                        })
                        st.markdown("---")

                    # Mostrar al final (después de todas las consultas)
                    st.markdown("### 📝 Respuestas del bot y Comentarios del análisis (final)")
                    for i, r in enumerate(resumen_final, start=1):
                        st.markdown(f"**{i}. {r['tipo']}**")
                        st.write(f"Respuesta del bot: {r['respuesta_bot']}")
                        st.write(f"Comentario análisis: {r['comentario_analisis']}")
                        st.markdown("---")
                else:
                    st.info("ℹ️ Esta sesión no tiene consultas registradas.")
            else:
                st.info("ℹ️ El usuario no tiene sesiones registradas.")
        else:
            st.info("👈 Busca y selecciona un usuario en el panel derecho.")
