from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes
import asyncio
from datetime import datetime
from translations import translations  # Importar las traducciones
from dotenv import load_dotenv
import os
from openai import OpenAI
from supabase import create_client
import re

load_dotenv()  # Carga las variables del archivo .env

# Configuración
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

# Crear cliente
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

client = OpenAI(
    api_key=os.environ.get("OPENAI_API_KEY"),
)

# Función para remover emojis de un texto
def remove_emojis(text):
    if not text:
        return text
    emoji_pattern = re.compile("["
                           u"\U0001F600-\U0001F64F"  # emoticons
                           u"\U0001F300-\U0001F5FF"  # symbols & pictographs
                           u"\U0001F680-\U0001F6FF"  # transport & map symbols
                           u"\U0001F700-\U0001F77F"  # alchemical symbols
                           u"\U0001F780-\U0001F7FF"  # Geometric Shapes
                           u"\U0001F800-\U0001F8FF"  # Supplemental Arrows-C
                           u"\U0001F900-\U0001F9FF"  # Supplemental Symbols and Pictographs
                           u"\U0001FA00-\U0001FA6F"  # Chess Symbols
                           u"\U0001FA70-\U0001FAFF"  # Symbols and Pictographs Extended-A
                           u"\U00002702-\U000027B0"  # Dingbats
                           u"\U000024C2-\U0001F251" 
                           "]+", flags=re.UNICODE)
    return emoji_pattern.sub(r'', text)

# Probar conexión
def probar_conexion():
    try:
        res = supabase.table("usuarios").select("*").limit(1).execute()
        print("Conexión correcta ✅", res.data)
    except Exception as e:
        print("Error de conexión ❌", e)

probar_conexion()


# Diccionario para almacenar las respuestas del usuario y datos de interacción
user_data = {}
interaction_data = {}  # Para almacenar datos básicos de usuario

# --------------------------------------------------------------------------------------------------------------------------------

# Función para obtener o registrar un usuario
def registrar_usuario(chat_id, nombre, identification_number):
    # Intentar buscar usuario
    res = supabase.table("usuarios").select("id").eq("chat_id", chat_id).execute()
    if res.data:
        return res.data[0]["id"]
    
    # Remover emojis antes de guardar en la BD
    nombre_limpio = remove_emojis(nombre) 
    id_number_limpio = remove_emojis(identification_number)
    
    # Si no existe, crearlo
    nuevo = supabase.table("usuarios").insert({
        "chat_id": chat_id,
        "nombre": nombre_limpio, 
        "identification_number": id_number_limpio
    }).execute()
    return nuevo.data[0]["id"]

# Función para verificar si el usuario tiene sesiones previas
def verificar_sesiones_previas(usuario_id):
    try:
        # Buscar las últimas sesiones del usuario (máximo 3) que tengan diagnóstico (consultas completas)
        # Primero obtenemos los IDs de sesiones que tienen un diagnóstico registrado
        res_diagnosticos = supabase.table("consultas").select("sesion_id").eq("tipo_mensaje", "diagnostico").execute()
        
        if not res_diagnosticos.data:
            print(f"No se encontraron diagnósticos para ninguna sesión del usuario {usuario_id}")
            return []
            
        # Extraer los IDs de sesiones que tienen diagnóstico
        sesiones_con_diagnostico = set(item['sesion_id'] for item in res_diagnosticos.data)
        print(f"Sesiones con diagnóstico encontradas: {len(sesiones_con_diagnostico)}")
        
        # Buscar sesiones del usuario que estén en el conjunto de sesiones con diagnóstico
        res = supabase.table("sesiones").select("id,fecha_inicio,estado").eq("usuario_id", usuario_id).order("fecha_inicio", desc=True).execute()
        
        # Verificar que tenemos datos
        if not res.data:
            print(f"No se encontraron sesiones para usuario {usuario_id}")
            return []
            
        # Filtrar solo las sesiones que tienen diagnóstico y eliminar duplicados
        unique_sessions = []
        seen_ids = set()
        for session in res.data:
            if session['id'] in sesiones_con_diagnostico and session['id'] not in seen_ids:
                seen_ids.add(session['id'])
                unique_sessions.append(session)
                if len(unique_sessions) >= 3:  # Limitar a 3 sesiones
                    break
                
        print(f"Sesiones finales para usuario {usuario_id}: {len(unique_sessions)}")
        if unique_sessions:
            print(f"IDs de sesiones: {[s['id'] for s in unique_sessions]}")
        return unique_sessions
    except Exception as e:
        print(f"Error al verificar sesiones previas: {str(e)}")
        return []

# Función para obtener diagnósticos de una sesión
def obtener_diagnostico_sesion(sesion_id):
    try:
        res = supabase.table("consultas").select("respuesta_bot").eq("sesion_id", sesion_id).eq("tipo_mensaje", "diagnostico").execute()
        if res.data and len(res.data) > 0:
            return res.data[0]["respuesta_bot"]
        return None
    except Exception as e:
        print(f"Error al obtener diagnóstico: {str(e)}")
        return None

# Función para obtener un resumen de los síntomas de una sesión
def obtener_resumen_sintomas(sesion_id):
    try:
        print(f"Obteniendo resumen para sesión ID: {sesion_id}")
        
        # Intentar obtener el diagnóstico (si existe)
        res_diagnostico = supabase.table("consultas").select("respuesta_bot").eq("sesion_id", sesion_id).eq("tipo_mensaje", "diagnostico").execute()
        print(f"Diagnósticos encontrados: {len(res_diagnostico.data) if res_diagnostico.data else 0}")
        
        # Buscar específicamente mensajes de tipo sintoma 
        res_sintomas = supabase.table("consultas").select("respuesta_usuario,tipo_mensaje").eq("sesion_id", sesion_id).eq("tipo_mensaje", "sintoma").execute()
        print(f"Mensajes de tipo 'sintoma' encontrados: {len(res_sintomas.data) if res_sintomas.data else 0}")
        
        # Buscar mensajes donde la columna 'pregunta' contenga información sobre síntomas
        res_preguntas = supabase.table("consultas").select("pregunta,respuesta_usuario").eq("sesion_id", sesion_id).execute()
        print(f"Total mensajes para buscar síntomas: {len(res_preguntas.data) if res_preguntas.data else 0}")
        
        # Obtener la fecha de la consulta
        res_fecha = supabase.table("sesiones").select("fecha_inicio").eq("id", sesion_id).execute()
        fecha_consulta = ""
        if res_fecha.data and len(res_fecha.data) > 0:
            fecha_consulta_raw = res_fecha.data[0].get("fecha_inicio", "")
            # Convertir la fecha a un formato más legible (solo fecha, sin hora)
            if fecha_consulta_raw:
                try:
                    fecha_dt = datetime.fromisoformat(fecha_consulta_raw.replace('Z', '+00:00'))
                    fecha_consulta = fecha_dt.strftime('%d/%m/%Y')
                except Exception as e:
                    print(f"Error al formatear fecha: {str(e)}")
                    fecha_consulta = fecha_consulta_raw.split('T')[0] if 'T' in fecha_consulta_raw else fecha_consulta_raw
        
        # Si no hay mensajes registrados
        if (not res_sintomas.data or len(res_sintomas.data) == 0) and (not res_preguntas.data or len(res_preguntas.data) == 0):
            if fecha_consulta:
                return f"{fecha_consulta} - Sin datos registrados"
            return "Sin datos registrados"
        
        # Buscar síntomas en mensajes específicos de tipo 'sintoma'
        sintoma_principal = ""
        if res_sintomas.data and len(res_sintomas.data) > 0:
            for item in res_sintomas.data:
                respuesta = item.get("respuesta_usuario", "")
                if respuesta and len(respuesta) > 3:  # Asegurar que es una respuesta válida
                    sintoma_principal = respuesta
                    print(f"Encontrado síntoma en tipo_mensaje=sintoma: {sintoma_principal[:50]}...")
                    break
        
        # Si no encontramos en tipo_mensaje, buscar en mensajes que contengan preguntas sobre síntomas
        if not sintoma_principal and res_preguntas.data:
            for item in res_preguntas.data:
                pregunta = item.get("pregunta", "").lower()
                respuesta = item.get("respuesta_usuario", "")
                if pregunta and respuesta and len(respuesta) > 3:
                    if any(keyword in pregunta for keyword in ["síntoma", "symptom", "dolor", "pain", "molestia", "discomfort", "qué te pasa", "what's wrong"]):
                        sintoma_principal = respuesta
                        print(f"Encontrado síntoma en pregunta sobre síntomas: {sintoma_principal[:50]}...")
                        break
        
        # Si aún no encontramos, tomar cualquier respuesta del usuario que parezca relevante
        if not sintoma_principal and res_preguntas.data:
            for item in res_preguntas.data:
                respuesta = item.get("respuesta_usuario", "")
                if respuesta and len(respuesta) > 10:  # Solo respuestas algo elaboradas
                    sintoma_principal = respuesta
                    print(f"Tomando respuesta larga como síntoma: {sintoma_principal[:50]}...")
                    break
        
        # Si hay un diagnóstico, mostrarlo junto con el síntoma principal
        if res_diagnostico.data and len(res_diagnostico.data) > 0:
            diagnostico = res_diagnostico.data[0]["respuesta_bot"]
            # Extraer la primera línea o frase del diagnóstico
            diagnostico_resumido = diagnostico.split('\n')[0]
            if len(diagnostico_resumido) > 50:
                diagnostico_resumido = diagnostico_resumido[:50] + "..."
            
            if sintoma_principal:
                resultado = f"{fecha_consulta} - {sintoma_principal[:50]}"
                return resultado[:80] + "..." if len(resultado) > 80 else resultado
            else:
                return f"{fecha_consulta} - {diagnostico_resumido[:50]}"
        
        # Si solo tenemos síntomas pero no diagnóstico
        if sintoma_principal:
            resultado = f"{fecha_consulta} - {sintoma_principal}"
            return resultado[:80] + "..." if len(resultado) > 80 else resultado
        else:
            return f"{fecha_consulta} - Consulta sin síntomas específicos"
            
    except Exception as e:
        print(f"Error al obtener resumen de síntomas: {str(e)}")
        return f"{fecha_consulta if fecha_consulta else 'Consulta'} - Error al obtener detalles"

# Función para crear sesión
def crear_sesion(usuario_id):
    # No hay texto con emojis aquí, pero mantenemos el patrón por consistencia
    res = supabase.table("sesiones").insert({
        "usuario_id": usuario_id,
        "fecha_inicio": datetime.now().isoformat(),
        "estado": "activa"
    }).execute()
    return res.data[0]["id"]

# ---------------------------------------------------------------------------------------------------------------------------------

def obtener_respuesta(idioma, clave, **kwargs):
    if idioma in translations:
        return translations[idioma].get(clave, "Lo siento, no entiendo tu mensaje.").format(**kwargs)
    else:
        return "Sorry, I can't detect your language."


def get_diagnosis(sintomas, idioma):
    try:
        # Si sintomas es un diccionario, convertir a texto
        if isinstance(sintomas, dict):
            sintomas = ", ".join(f"{k}: {v}" for k, v in sintomas.items())

        # Prompt único, dependiendo del idioma
        if idioma == 'en':
            prompt = (
                f"The user reports the following symptoms: {sintomas}. "
                "Return:\n1. Possible preliminary diagnoses.\n"
                "2. Home treatments.\n"
                "3. When to seek medical attention.\n"
                "Respond in plain English."
            )
        else:
            prompt = (
                f"El usuario reporta los siguientes síntomas: {sintomas}. "
                "Devuelve:\n1. Posibles diagnósticos preliminares.\n"
                "2. Tratamientos caseros.\n"
                "3. Cuándo debe buscar atención médica.\n"
                "Responde en texto plano."
            )

        # Consulta a OpenAI en un solo mensaje
        response = client.chat.completions.create(
            model="gpt-4o-mini",  # más económico que gpt-4o
            messages=[
                {"role": "system", "content": "You are a virtual doctor providing preliminary diagnoses based on reported symptoms."},
                {"role": "user", "content": prompt}
            ]
        )

        # Extraer respuesta
        return response.choices[0].message.content.strip()

    except Exception as e:
        print(f"Error en get_diagnosis: {str(e)}")
        return "Hubo un error al obtener el diagnóstico. Intenta nuevamente más tarde."


# Función para el comando /start o mensajes de saludo
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        user_id = update.effective_user.id
        user_name = update.effective_user.username or "Desconocido"
        chat_id = update.effective_chat.id
        timestamp = update.message.date

        # Verificar si el usuario ya está registrado
        res = supabase.table("usuarios").select("id").eq("chat_id", chat_id).execute()
        if res.data:
            # Si ya está registrado, obtener su ID
            usuario_id = res.data[0]["id"]
            
            # Guardar datos básicos del usuario en memoria
            interaction_data[user_id] = {
                'user_id': user_id,
                'user_name': user_name,
                'chat_id': chat_id,
                'start_time': timestamp,
                'messages_exchanged': 1,
                'confirmation_status': None,
                'satisfaction_status': None,
                'inactivity_flag': False,
                'usuario_id': usuario_id,  # ID en la base de datos
                'esperando_documento': False
            }
            
            # Mostrar opciones de idioma primero
            keyboard = [
                [InlineKeyboardButton("Español", callback_data="lang_es_existing")],
                [InlineKeyboardButton("English", callback_data="lang_en_existing")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await update.message.reply_text(
                "Please select your language / Por favor, selecciona tu idioma:",
                reply_markup=reply_markup
            )
            
            # Marcar que el usuario existe en el sistema
            user_data[user_id] = {
                'start_time': datetime.now(),
                'usuario_existe': True
            }
            
            print(f"[INICIO] Usuario registrado: UsuarioID={usuario_id}, TelegramID={user_id}, Usuario={user_name}")
            return
            
        else:
            # Si es nuevo usuario, guardar en memoria temporalmente
            # Flujo: 1. Seleccionar idioma -> 2. Ingresar documento -> 3. Continuar con consulta
            interaction_data[user_id] = {
                'user_id': user_id,
                'user_name': user_name,
                'chat_id': chat_id,
                'start_time': timestamp,
                'messages_exchanged': 1,
                'confirmation_status': None,
                'satisfaction_status': None,
                'inactivity_flag': False,
                'nuevo_usuario': True  # Marcar como nuevo usuario
            }
            
            # Pedir idioma primero
            keyboard = [
                [InlineKeyboardButton("Español", callback_data="lang_es_nuevo")],
                [InlineKeyboardButton("English", callback_data="lang_en_nuevo")]
          
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await update.message.reply_text(
                "Welcome! Please select your language / ¡Bienvenido! Por favor, selecciona tu idioma:",
                reply_markup=reply_markup
            )
            return
        
        # Si ya tenemos el usuario registrado, verificar sesiones previas
        sesiones_previas = verificar_sesiones_previas(usuario_id)
        
        # Si tiene sesiones previas, preguntar si quiere ver historial o iniciar nueva consulta
        if sesiones_previas:
            # Guardar datos básicos del usuario en memoria
            interaction_data[user_id] = {
                'user_id': user_id,
                'user_name': user_name,
                'chat_id': chat_id,
                'start_time': timestamp,
                'messages_exchanged': 1,
                'confirmation_status': None,
                'satisfaction_status': None,
                'inactivity_flag': False,
                'usuario_id': usuario_id,  # ID en la base de datos
                'sesiones_previas': sesiones_previas,
                'esperando_documento': False
            }
            
            # Mostrar opciones de idioma primero
            keyboard = [
                [InlineKeyboardButton("Español", callback_data="lang_es")],
                [InlineKeyboardButton("English", callback_data="lang_en")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await update.message.reply_text(
                "Please select your language / Por favor, selecciona tu idioma:",
                reply_markup=reply_markup
            )
            
            # Marcar que el usuario está en el flujo de sesiones previas
            user_data[user_id] = {
                'start_time': datetime.now(),
                'tiene_historial': True
            }
            
            print(f"[INICIO] Usuario registrado: UsuarioID={usuario_id}, TelegramID={user_id}, Usuario={user_name}, Sesiones previas: {len(sesiones_previas)}")
            
        else:
            # Si no tiene sesiones previas, crear una nueva sesión directamente
            sesion_id = crear_sesion(usuario_id)
            
            # Guardar en memoria para seguimiento en la conversación
            interaction_data[user_id] = {
                'user_id': user_id,
                'user_name': user_name,
                'chat_id': chat_id,
                'start_time': timestamp,
                'messages_exchanged': 1,
                'confirmation_status': None,
                'satisfaction_status': None,
                'inactivity_flag': False,
                'sesion_id': sesion_id,
                'usuario_id': usuario_id,
                'esperando_documento': False
            }
            user_data[user_id] = {'sintomas': [], 'start_time': datetime.now(), 'tiene_historial': False}

            # Log en consola
            print(f"[INICIO] Nuevo usuario: UsuarioID={usuario_id}, SesionID={sesion_id}, TelegramID={user_id}, Usuario={user_name}")

            # Mostrar opciones de idioma
            keyboard = [
                [InlineKeyboardButton("Español", callback_data="lang_es")],
                [InlineKeyboardButton("English", callback_data="lang_en")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await update.message.reply_text(
                "Please select your language / Por favor, selecciona tu idioma:",
                reply_markup=reply_markup
            )

    except Exception as e:
        print(f"Error al iniciar la conversación: {str(e)}")
        error_details = str(e)
        if user_id in interaction_data:
            interaction_data[user_id]['error_details'] = error_details
        await update.message.reply_text("An error occurred while starting the conversation. Please try again.")

    

# Función para manejar la selección de idioma
async def set_language(update: Update, context):
    query = update.callback_query
    user_id = query.from_user.id
    callback_data = query.data

    # Comprobar el tipo de flujo basado en el callback_data
    es_nuevo_usuario = False
    es_usuario_existente = False
    
    if callback_data == "lang_es_nuevo":
        idioma = 'es'
        es_nuevo_usuario = True
    elif callback_data == "lang_en_nuevo":
        idioma = 'en'
        es_nuevo_usuario = True
    elif callback_data == "lang_es_existing":
        idioma = 'es'
        es_usuario_existente = True
    elif callback_data == "lang_en_existing":
        idioma = 'en'
        es_usuario_existente = True
    elif callback_data == "lang_es":
        idioma = 'es'
    elif callback_data == "lang_en":
        idioma = 'en'
    else:
        idioma = 'en'

    # Guardar el idioma seleccionado
    if user_id not in user_data:
        user_data[user_id] = {}
    user_data[user_id]['idioma'] = idioma

    # Si es un usuario existente, continuar directamente con el paciente actual
    if es_usuario_existente and user_id in user_data and user_data[user_id].get('usuario_existe', False):
        usuario_id = interaction_data[user_id].get('usuario_id')
        
        # Verificar si el usuario tiene sesiones previas
        sesiones_previas = verificar_sesiones_previas(usuario_id)
        
        print(f"Sesiones previas encontradas para usuario {usuario_id}: {len(sesiones_previas)}")
        
        if sesiones_previas:
            # Guardar información de sesiones previas
            interaction_data[user_id]['sesiones_previas'] = sesiones_previas
            user_data[user_id]['tiene_historial'] = True
            
            # Crear opciones con las fechas de las sesiones anteriores
            keyboard = []
            for i, sesion in enumerate(sesiones_previas):
                # Obtener resumen de síntomas para esta sesión
                resumen = obtener_resumen_sintomas(sesion['id'])
                print(f"Resumen obtenido para sesión {sesion['id']}: {resumen}")
                
                keyboard.append([InlineKeyboardButton(
                    f"📋 {resumen}" if idioma == 'es' else f"📋 {resumen}", 
                    callback_data=f"historial_{sesion['id']}"
                )])
            
            # Añadir opción de nueva consulta
            keyboard.append([InlineKeyboardButton(
                "🆕 Nueva consulta" if idioma == 'es' else "🆕 New consultation",
                callback_data="nueva_consulta"
            )])
            
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            # Mostrar mensaje según el idioma
            mensaje = f"📜 <b>Se encontraron {len(sesiones_previas)} consultas previas:</b>\nSelecciona una para ver detalles o inicia una nueva:" if idioma == 'es' else \
                      f"📜 <b>{len(sesiones_previas)} previous consultations found:</b>\nSelect one to see details or start a new one:"
            
            await query.edit_message_text(text=mensaje, reply_markup=reply_markup, parse_mode="HTML")
            
        else:
            # Si no tiene sesiones previas, crear una nueva sesión directamente
            sesion_id = crear_sesion(usuario_id)
            
            interaction_data[user_id]['sesion_id'] = sesion_id
            user_data[user_id]['sintomas'] = []
            user_data[user_id]['tiene_historial'] = False
            
            # Mensaje de bienvenida y flujo normal
            await query.message.reply_text(obtener_respuesta(idioma, 'bienvenida'))
            await query.message.reply_text(obtener_respuesta(idioma, 'introduccion', user_name=query.from_user.username))
            
            print(f"[INICIO] Continuación con usuario existente: UsuarioID={usuario_id}, SesionID={sesion_id}, TelegramID={user_id}, Usuario={interaction_data[user_id]['user_name']}")
        return
        
    # Si es un nuevo usuario, solicitar documento de identidad
    if es_nuevo_usuario and user_id in interaction_data and interaction_data[user_id].get('nuevo_usuario', False):
        # Inicializar user_data si no existe
        if user_id not in user_data:
            user_data[user_id] = {}
        user_data[user_id]['idioma'] = idioma
        user_data[user_id]['start_time'] = datetime.now()
        
        # Marcar que estamos esperando el documento
        interaction_data[user_id]['esperando_documento'] = True
        
        # Solicitar documento en el idioma seleccionado
        if idioma == 'es':
            mensaje = "Por favor, ingresa tu número de documento de identidad. Este dato se utiliza únicamente para llevar un registro de tus consultas médicas."
        else:
            mensaje = "Please enter your identification number. This information is used only to keep track of your medical consultations."
        
        await query.message.reply_text(mensaje)
        return

    # Si el usuario tiene historial, preguntarle si quiere consultar historial o nueva consulta
    if user_data[user_id].get('tiene_historial', False) and user_id in interaction_data:
        sesiones_previas = interaction_data[user_id].get('sesiones_previas', [])
        if sesiones_previas:
            # Crear opciones con las fechas de las sesiones anteriores
            keyboard = []
            for i, sesion in enumerate(sesiones_previas):
                # Obtener resumen de síntomas para esta sesión
                resumen = obtener_resumen_sintomas(sesion['id'])
                
                keyboard.append([InlineKeyboardButton(
                    f"Consulta: {resumen}" if idioma == 'es' else f"Session: {resumen}", 
                    callback_data=f"historial_{sesion['id']}"
                )])
            
            # Añadir opción de nueva consulta
            keyboard.append([InlineKeyboardButton(
                "🆕 Nueva consulta" if idioma == 'es' else "🆕 New consultation",
                callback_data="nueva_consulta"
            )])
            
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            # Mostrar mensaje según el idioma
            mensaje = "Detectamos consultas previas. ¿Deseas ver alguna de estas o iniciar una nueva?" if idioma == 'es' else \
                      "We detected previous consultations. Would you like to see one of these or start a new one?"
            
            await query.message.reply_text(mensaje, reply_markup=reply_markup)
            return
    
    # Si no tiene historial o se está iniciando una nueva consulta directamente
    usuario_id = interaction_data[user_id].get('usuario_id')
    if 'sesion_id' not in interaction_data[user_id]:
        # Crear una nueva sesión
        sesion_id = crear_sesion(usuario_id)
        interaction_data[user_id]['sesion_id'] = sesion_id
        if 'sintomas' not in user_data[user_id]:
            user_data[user_id]['sintomas'] = []
    
    # Mensaje de bienvenida y flujo normal
    await query.message.reply_text(obtener_respuesta(idioma, 'bienvenida'))
    await query.message.reply_text(obtener_respuesta(idioma, 'introduccion', user_name=query.from_user.username))

# Función para manejar la inactividad
async def reset_after_inactivity(user_id, context):
    try:
        await asyncio.sleep(1800)  # Esperar 30 minutos

        if user_id in user_data:
            sesion_id = interaction_data[user_id].get("sesion_id")

            if sesion_id:
                # Guardar cierre en BD
                supabase.table("sesiones").update({
                    "fecha_fin": datetime.now().isoformat(),
                    "estado": "finalizada"
                }).eq("id", sesion_id).execute()

            # Registrar inactividad antes de eliminar datos
            if user_id in interaction_data:
                interaction_data[user_id]['inactivity_flag'] = True
                interaction_data[user_id]['end_time'] = datetime.now()
                print(f"[INACTIVIDAD] Usuario {user_id} - Sesión {sesion_id} cerrada por inactividad")

            # Limpiar datos en memoria
            user_data.pop(user_id, None)
            interaction_data.pop(user_id, None)

            # Avisar al usuario
            await context.bot.send_message(chat_id=user_id, text=obtener_respuesta('es', 'inactividad'))

    except Exception as e:
        print(f"Error en la función de inactividad: {str(e)}")
        if user_id in interaction_data:
            interaction_data[user_id]['error_details'] = str(e)



def guardar_respuestas_sintomas(sesion_id, sintomas_info):
    for pregunta, respuesta in sintomas_info.items():
        # Remover emojis antes de guardar en la base de datos
        pregunta_limpia = remove_emojis(pregunta)
        respuesta_limpia = remove_emojis(respuesta)
        
        supabase.table("consultas").insert({
            "sesion_id": sesion_id,
            "tipo_mensaje": "pregunta_sintomas",
            "pregunta": pregunta_limpia,
            "respuesta_usuario": respuesta_limpia
        }).execute()
        print(f"[BD] Guardado mensaje sin emojis - Pregunta: {pregunta_limpia[:20]}...")

# Función para manejar mensajes de texto
async def handle_message(update: Update, context):
    try:
        user_id = update.effective_user.id
        user_response = update.message.text
        timestamp = update.message.date  # Para registrar el tiempo de la respuesta

        # Verificar si estamos esperando el documento de identidad del usuario
        if user_id in interaction_data and interaction_data[user_id].get('esperando_documento', False):
            chat_id = interaction_data[user_id]['chat_id']
            user_name = interaction_data[user_id]['user_name']
            
            # Verificar que tenemos idioma
            if user_id not in user_data or 'idioma' not in user_data[user_id]:
                # Si por alguna razón no tenemos idioma, usar español por defecto
                user_data[user_id] = {'idioma': 'es', 'start_time': datetime.now()}
            
            idioma = user_data[user_id]['idioma']
            
            # Registrar usuario con su documento de identidad
            usuario_id = registrar_usuario(chat_id, user_name, user_response)
            
            # Verificar si el usuario tiene sesiones previas
            sesiones_previas = verificar_sesiones_previas(usuario_id)
            print(f"Sesiones previas para usuario ID {usuario_id}: {len(sesiones_previas)}, IDs: {[s['id'] for s in sesiones_previas]}")
            
            # Actualizar estado 
            interaction_data[user_id]['esperando_documento'] = False
            interaction_data[user_id]['usuario_id'] = usuario_id
            
            # Mensaje de agradecimiento
            if idioma == 'es':
                await update.message.reply_text("Gracias por proporcionar tu información.")
            else:
                await update.message.reply_text("Thank you for providing your information.")
            
            # Establecer el resto de datos según si tiene sesiones previas o no
            if sesiones_previas:
                interaction_data[user_id]['sesiones_previas'] = sesiones_previas
                # Asegurarnos de mantener el idioma y el start_time
                user_data[user_id]['tiene_historial'] = True
                
                # Crear opciones con las fechas de las sesiones anteriores
                keyboard = []
                print(f"Generando botones para {len(sesiones_previas)} sesiones previas")
                for i, sesion in enumerate(sesiones_previas):
                    # Obtener resumen de síntomas para esta sesión
                    resumen = obtener_resumen_sintomas(sesion['id'])
                    print(f"Botón {i+1}: Sesión ID {sesion['id']} - Resumen: {resumen}")
                    
                    # Añadir emoji para mejor visualización
                    keyboard.append([InlineKeyboardButton(
                        f"📋 {resumen}" if idioma == 'es' else f"📋 {resumen}", 
                        callback_data=f"historial_{sesion['id']}"
                    )])
                
                # Añadir opción de nueva consulta
                keyboard.append([InlineKeyboardButton(
                    "🆕 Nueva consulta" if idioma == 'es' else "🆕 New consultation",
                    callback_data="nueva_consulta"
                )])
                
                reply_markup = InlineKeyboardMarkup(keyboard)
                
                # Mostrar mensaje según el idioma
                mensaje = "📜 <b>Consultas previas detectadas:</b>\nSelecciona una para ver detalles o inicia una nueva:" if idioma == 'es' else \
                          "📜 <b>Previous consultations detected:</b>\nSelect one to see details or start a new one:"
                
                await update.message.reply_text(mensaje, reply_markup=reply_markup, parse_mode="HTML")
                print(f"[INICIO] Usuario registrado: UsuarioID={usuario_id}, TelegramID={user_id}, Usuario={user_name}, Sesiones previas: {len(sesiones_previas)}")
            else:
                # Si no tiene sesiones previas, crear una nueva sesión directamente
                sesion_id = crear_sesion(usuario_id)
                interaction_data[user_id]['sesion_id'] = sesion_id
                # Asegurarnos de mantener el idioma y start_time
                user_data[user_id]['sintomas'] = []
                user_data[user_id]['tiene_historial'] = False
                
                # Mensaje de bienvenida y flujo normal
                await update.message.reply_text(obtener_respuesta(idioma, 'bienvenida'))
                await update.message.reply_text(obtener_respuesta(idioma, 'introduccion', user_name=update.effective_user.username))
                print(f"[INICIO] Nuevo usuario: UsuarioID={usuario_id}, SesionID={sesion_id}, TelegramID={user_id}, Usuario={user_name}")
                
            return

        if user_id not in user_data:
            await start(update, context)
            return
        
        # A partir de aquí, convertir a minúsculas para el procesamiento
        user_response = user_response.lower()
        
        # Incrementar contador de mensajes intercambiados
        if user_id in interaction_data:
            interaction_data[user_id]['messages_exchanged'] = interaction_data[user_id].get('messages_exchanged', 0) + 1
        
        # Verificar si estamos esperando una sugerencia
        if user_data[user_id].get('esperando_sugerencia', False):
            idioma = user_data[user_id]['idioma']
            sesion_id = interaction_data[user_id].get("sesion_id")
            
            # Guardar la sugerencia en interaction_data
            interaction_data[user_id]['user_feedback'] = user_response
            print(f"[FEEDBACK] Usuario {user_id} envió: {user_response}")
            
            # Guardar el feedback en la tabla sesiones
            if sesion_id:
                try:
                    supabase.table("sesiones").update({
                        "feedback_usuario": user_response
                    }).eq("id", sesion_id).execute()
                    print(f"[BD] Feedback guardado para sesión {sesion_id}")
                except Exception as e:
                    print(f"Error al guardar feedback en BD: {str(e)}")
            
            # Agregar campo de calificación
            keyboard = [
                [InlineKeyboardButton("1 ⭐", callback_data="rating_1"),
                 InlineKeyboardButton("2 ⭐⭐", callback_data="rating_2"),
                 InlineKeyboardButton("3 ⭐⭐⭐", callback_data="rating_3"),
                 InlineKeyboardButton("4 ⭐⭐⭐⭐", callback_data="rating_4"),
                 InlineKeyboardButton("5⭐⭐⭐⭐⭐", callback_data="rating_5")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await update.message.reply_text(
                obtener_respuesta(idioma, 'opinion'),
                reply_markup=reply_markup
            )
            
            # Reiniciar el estado
            user_data[user_id]['esperando_sugerencia'] = False
            return
        
        # Verificar si estamos esperando una corrección
        if user_data[user_id].get('esperando_correccion', False):
            # Obtener el índice de la pregunta que se está corrigiendo
            corrigiendo_index = user_data[user_id].get('corrigiendo_index')
            idioma = user_data[user_id]['idioma']
            
            if corrigiendo_index is not None:
                # Actualizar la respuesta en el arreglo de síntomas
                user_data[user_id]['sintomas'][corrigiendo_index] = user_response
                
                # Actualizar sintomas_info
                preguntas = user_data[user_id].get('preguntas', [])
                if corrigiendo_index < len(preguntas):
                    pregunta = preguntas[corrigiendo_index]
                    user_data[user_id]['sintomas_info'][pregunta] = user_response
                
                # Mostrar mensaje de confirmación
                await update.message.reply_text(
                    "✅ Respuesta actualizada. ¿Deseas corregir otra respuesta?" if idioma == 'es' else 
                    "✅ Answer updated. Do you want to correct another answer?"
                )
                
                # Crear teclado con opciones para seguir corrigiendo o finalizar
                keyboard = []
                for i, pregunta in enumerate(preguntas):
                    texto_boton = pregunta[:60] + ('...' if len(pregunta) > 60 else '')
                    keyboard.append([InlineKeyboardButton(f"{i+1}. {texto_boton}", callback_data=f"corregir_{i}")])
                
                # Añadir botón para finalizar correcciones
                keyboard.append([
                    InlineKeyboardButton(
                        "✓ Finalizar correcciones" if idioma == 'es' else "✓ Finish corrections",
                        callback_data="finalizar_correccion"
                    )
                ])
                
                reply_markup = InlineKeyboardMarkup(keyboard)
                await update.message.reply_text(
                    "Selecciona otra respuesta para corregir o finaliza:" if idioma == 'es' else
                    "Select another answer to correct or finish:",
                    reply_markup=reply_markup
                )
                
                # Reiniciar el estado de corrección
                user_data[user_id]['esperando_correccion'] = False
                user_data[user_id]['corrigiendo_index'] = None
                
                return
        
        # Si no estamos en modo corrección, continuar con el flujo normal
        # Registrar y actualizar síntomas
        idioma = user_data[user_id]['idioma']
        user_data[user_id]['sintomas'].append(user_response)

        # Enviar la pregunta correspondiente según la cantidad de síntomas proporcionados
        if len(user_data[user_id]['sintomas']) == 1:
            await update.message.reply_text(obtener_respuesta(idioma, 'pregunta_sintomas_1'), parse_mode='Markdown')  # ¿Desde cuándo comenzaron estos síntomas?
        elif len(user_data[user_id]['sintomas']) == 2:
            await update.message.reply_text(obtener_respuesta(idioma, 'pregunta_sintomas_2'), parse_mode='Markdown')  # En escala de 1 a 10, ¿cómo calificarías tus síntomas?
        elif len(user_data[user_id]['sintomas']) == 3:
            await update.message.reply_text(obtener_respuesta(idioma, 'pregunta_sintomas_3'))  # ¿Con qué frecuencia ocurren tus síntomas?
        elif len(user_data[user_id]['sintomas']) == 4:
            await update.message.reply_text(obtener_respuesta(idioma, 'pregunta_sintomas_4'))  # ¿Has notado algún cambio reciente en tus síntomas?
        elif len(user_data[user_id]['sintomas']) == 5:
            await update.message.reply_text(obtener_respuesta(idioma, 'pregunta_sintomas_5'))  # ¿Hay algún otro dato relevante, como caídas o incidentes recientes?
        elif len(user_data[user_id]['sintomas']) == 6:
            await update.message.reply_text(obtener_respuesta(idioma, 'pregunta_sintomas_6'))  # ¿Tienes algún antecedente médico o enfermedad importante?
        elif len(user_data[user_id]['sintomas']) == 7:
            await update.message.reply_text(obtener_respuesta(idioma, 'pregunta_sintomas_7'))  # ¿Presenta alguna enfermedad crónica?
        elif len(user_data[user_id]['sintomas']) == 8:
            await update.message.reply_text(obtener_respuesta(idioma, 'pregunta_sintomas_8'))  # Indique si es alérgico a algún medicamento o alimento.
        elif len(user_data[user_id]['sintomas']) == 9:
            await update.message.reply_text(obtener_respuesta(idioma, 'pregunta_sintomas_9'))  # Indique su edad.
        elif len(user_data[user_id]['sintomas']) == 10:
            await update.message.reply_text(obtener_respuesta(idioma, 'pregunta_sintomas_10'))  # Indique su sexo (masculino, femenino).
        elif len(user_data[user_id]['sintomas']) == 11:
            await update.message.reply_text(obtener_respuesta(idioma, 'pregunta_sintomas_11'))  # Indique su peso (kg).
        elif len(user_data[user_id]['sintomas']) == 12:
            await update.message.reply_text(obtener_respuesta(idioma, 'pregunta_sintomas_12'))  # Indique su altura (cm).
        elif len(user_data[user_id]['sintomas']) == 13:            
            # Crear información de síntomas
            sintomas_info = {
                remove_emojis(obtener_respuesta(idioma, 'descripcion_sintomas')): remove_emojis(user_data[user_id]['sintomas'][0]),  # Síntomas principales   
                remove_emojis(obtener_respuesta(idioma, 'duracion_sintomas')): remove_emojis(user_data[user_id]['sintomas'][1]),  # Duración
                remove_emojis(obtener_respuesta(idioma, 'intensidad_sintomas')): remove_emojis(user_data[user_id]['sintomas'][2]),  # Intensidad
                remove_emojis(obtener_respuesta(idioma, 'frecuencia_sintomas')): remove_emojis(user_data[user_id]['sintomas'][3]),  # Frecuencia
                remove_emojis(obtener_respuesta(idioma, 'cambios_sintomas')): remove_emojis(user_data[user_id]['sintomas'][4]),  # Cambios recientes
                remove_emojis(obtener_respuesta(idioma, 'datos_relevantes')): remove_emojis(user_data[user_id]['sintomas'][5]),  # Datos relevantes
                remove_emojis(obtener_respuesta(idioma, 'antecedentes_medicos')): remove_emojis(user_data[user_id]['sintomas'][6]),  # Antecedentes médicos
                remove_emojis(obtener_respuesta(idioma, 'enfermedades_cronicas')): remove_emojis(user_data[user_id]['sintomas'][7]),  # Enfermedades crónicas
                remove_emojis(obtener_respuesta(idioma, 'alergias')): remove_emojis(user_data[user_id]['sintomas'][8]),  # Alergias
                remove_emojis(obtener_respuesta(idioma, 'edad')): remove_emojis(user_data[user_id]['sintomas'][9]),  # Edad
                remove_emojis(obtener_respuesta(idioma, 'sexo')): remove_emojis(user_data[user_id]['sintomas'][10]),  # Sexo
                remove_emojis(obtener_respuesta(idioma, 'peso')): remove_emojis(user_data[user_id]['sintomas'][11]),  # Peso
                remove_emojis(obtener_respuesta(idioma, 'altura')): remove_emojis(user_data[user_id]['sintomas'][12])  # Altura
            }

            # Guardar en user_data para uso futuro
            user_data[user_id]['sintomas_info'] = sintomas_info
            
            # Formato de texto para la interacción con el usuario
            sintomas_text = "\n".join(
                [f"<b>{key}</b>: {value}" for key, value in sintomas_info.items()]
            )
            
            # Crear teclado
            keyboard = [
                [InlineKeyboardButton(obtener_respuesta(idioma, 'confirm_yes'), callback_data="confirm_yes")],
                [InlineKeyboardButton(obtener_respuesta(idioma, 'confirm_no'), callback_data="confirm_no")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            print(reply_markup)

            # Enviar mensaje con formato HTML
            await update.message.reply_text(
                obtener_respuesta(idioma, 'confirmacion_sintomas', sintomas_text=sintomas_text),
                reply_markup=reply_markup,
                parse_mode="HTML"
            )
            
    except Exception as e:
        print(f"Error al manejar el mensaje del usuario: {str(e)}")
        if user_id in interaction_data:
            interaction_data[user_id]['error_details'] = str(e)
        await update.message.reply_text(obtener_respuesta('es', 'error_mensaje'))

# Nueva función para manejar las correcciones
async def handle_correction(update: Update, context):
    try:
        query = update.callback_query
        user_id = query.from_user.id
        callback_data = query.data
        
        if user_id not in user_data:
            await query.message.reply_text("Parece que la sesión ha expirado. Usa /start para reiniciar.")
            return
        
        idioma = user_data[user_id]['idioma']
        
        if callback_data.startswith("corregir_"):
            # Obtener el índice de la pregunta a corregir
            pregunta_index = int(callback_data.split("_")[1])
            preguntas = user_data[user_id].get('preguntas', [])
            
            if pregunta_index < len(preguntas):
                # Guardar el índice para saber qué respuesta estamos corrigiendo
                user_data[user_id]['corrigiendo_index'] = pregunta_index
                
                # Enviar la pregunta al usuario
                await query.message.reply_text(f"{preguntas[pregunta_index]}")
                
                # Actualizar el estado para indicar que estamos esperando una corrección
                user_data[user_id]['esperando_correccion'] = True
            else:
                await query.message.reply_text("Error al seleccionar la pregunta para corregir.")
        elif callback_data == "finalizar_correccion":
            # Regenerar la confirmación con los datos actualizados
            sintomas_info = user_data[user_id].get('sintomas_info', {})
            
            # Crear texto formateado en HTML
            sintomas_text = "\n".join(
                [f"<b>{key}</b>: {value}" for key, value in sintomas_info.items()]
            )
            
            # Crear teclado de confirmación
            keyboard = [
                [InlineKeyboardButton(obtener_respuesta(idioma, 'confirm_yes'), callback_data="confirm_yes")],
                [InlineKeyboardButton(obtener_respuesta(idioma, 'confirm_no'), callback_data="confirm_no")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            # Enviar mensaje con formato HTML actualizado
            await query.message.reply_text(
                obtener_respuesta(idioma, 'confirmacion_sintomas', sintomas_text=sintomas_text),
                reply_markup=reply_markup,
                parse_mode="HTML"
            )
    except Exception as e:
        print(f"Error al manejar la corrección: {str(e)}")
        await query.message.reply_text("Error al procesar tu solicitud de corrección.")        

async def handle_confirmation(update: Update, context):
    try:
        query = update.callback_query
        user_id = query.from_user.id
        user_choice = query.data  # 'confirm_yes' o 'confirm_no'

        if user_id not in user_data or 'start_time' not in user_data[user_id]:
            await query.message.reply_text("Parece que la sesión ha expirado. Usa /start para reiniciar.")
            return

        idioma = user_data[user_id]['idioma']
        sintomas_info = user_data[user_id].get('sintomas_info', {})
        sesion_id = interaction_data[user_id].get("sesion_id")

        # Guardar estado de confirmación
        interaction_data[user_id]['confirmation_status'] = "Sí" if user_choice == "confirm_yes" else "No"

        # Usuario elige NO → flujo de corrección
        if user_choice == "confirm_no":
            preguntas = [
                obtener_respuesta(idioma, 'descripcion_sintomas'),
                obtener_respuesta(idioma, 'duracion_sintomas'),
                obtener_respuesta(idioma, 'intensidad_sintomas'),
                obtener_respuesta(idioma, 'frecuencia_sintomas'),
                obtener_respuesta(idioma, 'cambios_sintomas'),
                obtener_respuesta(idioma, 'datos_relevantes'),
                obtener_respuesta(idioma, 'antecedentes_medicos'),
                obtener_respuesta(idioma, 'enfermedades_cronicas'),
                obtener_respuesta(idioma, 'alergias'),
                obtener_respuesta(idioma, 'edad'),
                obtener_respuesta(idioma, 'sexo'),
                obtener_respuesta(idioma, 'peso'),
                obtener_respuesta(idioma, 'altura')
            ]
            user_data[user_id]['preguntas'] = preguntas
            keyboard = []
            for i, pregunta in enumerate(preguntas):
                texto_boton = pregunta[:60] + ('...' if len(pregunta) > 60 else '')
                keyboard.append([InlineKeyboardButton(f"{i+1}. {texto_boton}", callback_data=f"corregir_{i}")])
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.message.reply_text(
                obtener_respuesta(idioma, 'seleccionar_correccion'),
                reply_markup=reply_markup
            )
            return

        # Usuario elige SÍ → Guardar en Supabase
        guardar_respuestas_sintomas(sesion_id, sintomas_info)

        print(f"[BD] {len(sintomas_info)} respuestas guardadas para sesión {sesion_id}")

        # Mensaje de espera
        espera_msg = obtener_respuesta(idioma, 'diagnostico_proceso')
        await query.message.reply_text(f"⏳ {espera_msg}")

        # Generar diagnóstico con ChatGPT
        sintomas_texto = "\n".join([f"{k}: {v}" for k, v in sintomas_info.items()])
        diagnostico = get_diagnosis(sintomas_texto, idioma)
        interaction_data[user_id]['diagnosis_provided'] = diagnostico

        # Remover emojis antes de guardar en la BD
        diagnostico_limpio = remove_emojis(diagnostico)
        pregunta_limpia = remove_emojis("Diagnóstico generado")
        
        # Guardar diagnóstico en la BD
        supabase.table("consultas").insert({
            "sesion_id": sesion_id,
            "tipo_mensaje": "diagnostico",
            "pregunta": pregunta_limpia,
            "respuesta_bot": diagnostico_limpio
        }).execute()

        print(f"[BD] Diagnóstico guardado para sesión {sesion_id} (sin emojis)")

        # Enviar diagnóstico al usuario (con formato)
        mensaje_diagnostico = "<b>🏥 RESULTADO DEL ANÁLISIS MÉDICO 🏥</b>\n\n" if idioma == 'es' else "<b>🏥 MEDICAL ANALYSIS RESULT 🏥</b>\n\n"
        mensaje_final = mensaje_diagnostico + diagnostico + "\n\n<i>⚠️ Este análisis es informativo y no reemplaza consulta médica.</i>"
        await query.message.reply_text(mensaje_final, parse_mode="HTML")

        # Preguntar satisfacción
        keyboard = [
            [InlineKeyboardButton(f"✅ {obtener_respuesta(idioma, 'satisfied_yes')}", callback_data="satisfied_yes")],
            [InlineKeyboardButton(f"❌ {obtener_respuesta(idioma, 'satisfied_no')}", callback_data="satisfied_no")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.message.reply_text(
            "¿Te ha sido útil este diagnóstico? 🤔" if idioma == 'es' else "Was this diagnosis helpful? 🤔",
            reply_markup=reply_markup
        )

    except Exception as e:
        print(f"Error en handle_confirmation: {e}")
        await query.message.reply_text(obtener_respuesta('es', 'error_confirmacion'))

# Manejar satisfacción del usuario
async def handle_satisfaction(update: Update, context):
    try:
        query = update.callback_query
        user_id = query.from_user.id
        idioma = user_data[user_id]['idioma']
        sesion_id = interaction_data[user_id].get("sesion_id")

        if query.data == "satisfied_yes":
            interaction_data[user_id]['satisfaccion'] = True
            await query.message.reply_text(obtener_respuesta(idioma, 'gracias'))
        elif query.data == "satisfied_no":
            interaction_data[user_id]['satisfaccion'] = False
            await query.message.reply_text(obtener_respuesta(idioma, 'disculpa'))

        # Guardar en la BD
        supabase.table("sesiones").update({
            "satisfaccion": interaction_data[user_id]['satisfaccion']
        }).eq("id", sesion_id).execute()

        # Pedir feedback
        user_data[user_id]['esperando_sugerencia'] = True
        await query.message.reply_text(obtener_respuesta(idioma, 'buzon'))

    except Exception as e:
        print(f"Error al manejar la satisfacción del usuario: {str(e)}")
        await query.message.reply_text(obtener_respuesta(idioma, 'error_satisfaccion'))


# (Eliminado) handle_feedback: la lógica de feedback ya se gestiona en handle_message cuando 'esperando_sugerencia' es True.

# Función para manejar la selección de historial o nueva consulta
async def handle_historial(update: Update, context):
    try:
        query = update.callback_query
        user_id = query.from_user.id
        callback_data = query.data
        
        if user_id not in user_data:
            await query.message.reply_text("Parece que la sesión ha expirado. Usa /start para reiniciar.")
            return
        
        idioma = user_data[user_id].get('idioma', 'es')
        
        # Si el usuario elige iniciar nueva consulta
        if callback_data == "nueva_consulta":
            # Crear nueva sesión
            usuario_id = interaction_data[user_id].get('usuario_id')
            sesion_id = crear_sesion(usuario_id)
            
            # Actualizar datos
            interaction_data[user_id]['sesion_id'] = sesion_id
            user_data[user_id]['sintomas'] = []
            user_data[user_id]['tiene_historial'] = False
            
            # Mostrar mensaje de bienvenida e introducción
            await query.message.reply_text(obtener_respuesta(idioma, 'bienvenida'))
            await query.message.reply_text(obtener_respuesta(idioma, 'introduccion', user_name=query.from_user.username))
            
            return
        
        # Si el usuario elige ver historial
        if callback_data.startswith("historial_"):
            sesion_id = int(callback_data.split('_')[1])
            print(f"Usuario {user_id} solicitó ver la sesión {sesion_id}")
            
            # Obtener diagnóstico de esa sesión
            diagnostico = obtener_diagnostico_sesion(sesion_id)
            
            # Obtener datos adicionales de la consulta
            try:
                # Obtener síntomas registrados para mostrar resumen
                res_sintomas = supabase.table("consultas").select("pregunta,respuesta_usuario").eq("sesion_id", sesion_id).eq("tipo_mensaje", "sintoma").execute()
                print(f"Síntomas encontrados para sesión {sesion_id}: {len(res_sintomas.data) if res_sintomas.data else 0}")
                
                # Obtener todos los mensajes para buscar síntomas en cualquier parte
                res_mensajes = supabase.table("consultas").select("pregunta,respuesta_usuario,tipo_mensaje").eq("sesion_id", sesion_id).execute()
                print(f"Total mensajes encontrados para sesión {sesion_id}: {len(res_mensajes.data) if res_mensajes.data else 0}")
                
                # Obtener fecha de la consulta
                res_fecha = supabase.table("sesiones").select("fecha_inicio").eq("id", sesion_id).execute()
                fecha_consulta = ""
                if res_fecha.data and len(res_fecha.data) > 0:
                    fecha_consulta_raw = res_fecha.data[0].get("fecha_inicio", "")
                    if fecha_consulta_raw:
                        try:
                            fecha_dt = datetime.fromisoformat(fecha_consulta_raw.replace('Z', '+00:00'))
                            fecha_consulta = fecha_dt.strftime('%d/%m/%Y %H:%M')
                        except:
                            fecha_consulta = fecha_consulta_raw
                
                # Construir resumen de síntomas
                sintomas_texto = ""
                
                # Primero intentar extraer de mensajes específicamente marcados como síntomas
                if res_sintomas.data and len(res_sintomas.data) > 0:
                    for i, item in enumerate(res_sintomas.data):
                        pregunta = item.get("pregunta", "")
                        respuesta = item.get("respuesta_usuario", "")
                        if pregunta and respuesta and len(respuesta) > 3:
                            titulo_pregunta = "🤒 Síntomas principales" if idioma == 'es' else "🤒 Main symptoms"
                            sintomas_texto += f"<b>{titulo_pregunta}:</b> {respuesta}\n"
                
                # Si no encontramos síntomas específicos, buscar en todos los mensajes
                if not sintomas_texto and res_mensajes.data:
                    print(f"Buscando síntomas en todos los mensajes para sesión {sesion_id}")
                    for i, item in enumerate(res_mensajes.data):
                        pregunta = item.get("pregunta", "").lower()
                        respuesta = item.get("respuesta_usuario", "")
                        tipo = item.get("tipo_mensaje", "")
                        
                        # Si encontramos una pregunta relacionada con síntomas
                        if pregunta and respuesta and len(respuesta) > 3:
                            titulo_pregunta = ""
                            # Identificar el tipo de pregunta para darle un título adecuado
                            if any(keyword in pregunta for keyword in ["síntoma", "symptom", "dolor", "pain", "molestia", "discomfort"]):
                                titulo_pregunta = "🤒 Síntomas principales" if idioma == 'es' else "🤒 Main symptoms"
                                sintomas_texto += f"<b>{titulo_pregunta}:</b> {respuesta}\n"
                                print(f"Síntoma encontrado en pregunta: {pregunta[:30]}")
                                break  # Ya tenemos el síntoma principal
                            
                # Si seguimos sin síntomas, tomar cualquier respuesta relevante
                if not sintomas_texto and res_mensajes.data:
                    print(f"Tomando cualquier respuesta relevante como síntoma para sesión {sesion_id}")
                    for i, item in enumerate(res_mensajes.data):
                        respuesta = item.get("respuesta_usuario", "")
                        if respuesta and len(respuesta) > 10:  # Solo respuestas elaboradas
                            titulo_pregunta = "ℹ️ Descripción del paciente" if idioma == 'es' else "ℹ️ Patient description"
                            sintomas_texto += f"<b>{titulo_pregunta}:</b> {respuesta}\n"
                            print(f"Usando respuesta larga como síntoma: {respuesta[:30]}")
                            break
            except Exception as e:
                print(f"Error al obtener detalles adicionales: {str(e)}")
                sintomas_texto = ""
            
            if diagnostico:
                # Preparar el encabezado según el idioma
                titulo = "<b>🏥 HISTORIAL: CONSULTA ANTERIOR 🏥</b>\n\n" if idioma == 'es' else "<b>🏥 HISTORY: PREVIOUS CONSULTATION 🏥</b>\n\n"
                
                # Incluir fecha si está disponible
                if fecha_consulta:
                    titulo += f"<b>📅 {'Fecha' if idioma == 'es' else 'Date'}:</b> {fecha_consulta}\n\n"
                
                # Añadir resumen de síntomas si está disponible
                mensaje_historial = ""
                if sintomas_texto:
                    mensaje_historial = f"<b>📋 {'RESUMEN DE SÍNTOMAS' if idioma == 'es' else 'SYMPTOMS SUMMARY'}:</b>\n{sintomas_texto}\n"
                else:
                    mensaje_historial = f"<b>📋 {'RESUMEN DE SÍNTOMAS' if idioma == 'es' else 'SYMPTOMS SUMMARY'}:</b>\n<i>{'No se encontraron síntomas detallados para esta consulta' if idioma == 'es' else 'No detailed symptoms found for this consultation'}</i>\n\n"
                    print(f"No se encontraron síntomas para la sesión {sesion_id}")
                
                # Añadir el diagnóstico
                mensaje_historial += f"<b>🔍 {'DIAGNÓSTICO' if idioma == 'es' else 'DIAGNOSIS'}:</b>\n{diagnostico}"
                
                # Mensaje final con advertencia
                mensaje_final = titulo + mensaje_historial + f"\n\n<i>⚠️ {'Este es un diagnóstico de una consulta anterior. Para una nueva consulta, usa /start.' if idioma == 'es' else 'This is a diagnosis from a previous consultation. For a new consultation, use /start.'}</i>"
                
                # Limitar el mensaje si es muy largo
                if len(mensaje_final) > 4000:  # Telegram tiene un límite de caracteres
                    mensaje_final = mensaje_final[:3950] + "...\n\n<i>⚠️ Mensaje truncado por longitud</i>"
                
                await query.message.reply_text(mensaje_final, parse_mode="HTML")
                
                # Ofrecer la opción de iniciar nueva consulta
                keyboard = [
                    [InlineKeyboardButton(
                        "🆕 Iniciar nueva consulta" if idioma == 'es' else "🆕 Start new consultation",
                        callback_data="nueva_consulta"
                    )]
                ]
                reply_markup = InlineKeyboardMarkup(keyboard)
                
                mensaje = "¿Deseas iniciar una nueva consulta?" if idioma == 'es' else "Would you like to start a new consultation?"
                await query.message.reply_text(mensaje, reply_markup=reply_markup)
            else:
                # Si no se encuentra el diagnóstico
                mensaje_error = "No pudimos encontrar el diagnóstico de esa sesión. ¿Deseas iniciar una nueva consulta?" if idioma == 'es' else \
                               "We couldn't find the diagnosis for that session. Would you like to start a new consultation?"
                
                keyboard = [
                    [InlineKeyboardButton(
                        "🆕 Nueva consulta" if idioma == 'es' else "🆕 New consultation",
                        callback_data="nueva_consulta"
                    )]
                ]
                reply_markup = InlineKeyboardMarkup(keyboard)
                
                await query.message.reply_text(mensaje_error, reply_markup=reply_markup)
    
    except Exception as e:
        print(f"Error al manejar historial: {str(e)}")
        idioma = user_data.get(user_id, {}).get('idioma', 'es')
        await query.message.reply_text(obtener_respuesta(idioma, 'error_mensaje'))

# Manejar calificación del usuario y cerrar sesión
# Función para manejar la selección del paciente (continuar con el actual o registrar nuevo)
async def handle_patient_selection(update: Update, context):
    try:
        query = update.callback_query
        user_id = query.from_user.id
        callback_data = query.data
        
        # Asegurarse de que tenemos los datos del usuario
        if user_id not in user_data or user_id not in interaction_data:
            await query.message.reply_text("Ocurrió un error. Por favor, inicia la conversación nuevamente con /start.")
            return
        
        idioma = user_data[user_id].get('idioma', 'es')  # Por defecto español si no hay idioma
        
        # Manejar los diferentes callbacks
        if callback_data == "continuar_paciente":
            # El usuario quiere continuar con el paciente actual
            usuario_id = interaction_data[user_id].get('usuario_id')
            
            # Verificar si el usuario tiene sesiones previas
            sesiones_previas = verificar_sesiones_previas(usuario_id)
            print(f"Continuar paciente: {len(sesiones_previas)} sesiones previas para usuario ID {usuario_id}")
            
            if sesiones_previas:
                # Guardar información de sesiones previas
                interaction_data[user_id]['sesiones_previas'] = sesiones_previas
                user_data[user_id]['tiene_historial'] = True
                
                # Crear opciones con las fechas de las sesiones anteriores
                keyboard = []
                print(f"Continuar paciente: Generando botones para {len(sesiones_previas)} sesiones previas")
                for i, sesion in enumerate(sesiones_previas):
                    # Obtener resumen de síntomas para esta sesión
                    resumen = obtener_resumen_sintomas(sesion['id'])
                    print(f"Botón {i+1}: Sesión ID {sesion['id']} - Resumen: {resumen}")
                    
                    keyboard.append([InlineKeyboardButton(
                        f"Consulta: {resumen}" if idioma == 'es' else f"Session: {resumen}", 
                        callback_data=f"historial_{sesion['id']}"
                    )])
                
                # Añadir opción de nueva consulta
                keyboard.append([InlineKeyboardButton(
                    "🆕 Nueva consulta" if idioma == 'es' else "🆕 New consultation",
                    callback_data="nueva_consulta"
                )])
                
                reply_markup = InlineKeyboardMarkup(keyboard)
                
                # Mostrar mensaje según el idioma
                mensaje = "Detectamos consultas previas. ¿Deseas ver alguna de estas o iniciar una nueva?" if idioma == 'es' else \
                          "We detected previous consultations. Would you like to see one of these or start a new one?"
                
                await query.edit_message_text(text=mensaje, reply_markup=reply_markup)
                
            else:
                # Si no tiene sesiones previas, crear una nueva sesión directamente
                sesion_id = crear_sesion(usuario_id)
                
                interaction_data[user_id]['sesion_id'] = sesion_id
                user_data[user_id]['sintomas'] = []
                user_data[user_id]['tiene_historial'] = False
                
                # Mensaje de bienvenida y flujo normal
                await query.message.reply_text(obtener_respuesta(idioma, 'bienvenida'))
                await query.message.reply_text(obtener_respuesta(idioma, 'introduccion', user_name=query.from_user.username))
                
                print(f"[INICIO] Continuación con usuario existente: UsuarioID={usuario_id}, SesionID={sesion_id}, TelegramID={user_id}, Usuario={interaction_data[user_id]['user_name']}")
        
        elif callback_data == "nuevo_paciente":
            # El usuario quiere registrar un nuevo paciente
            # Marcamos que estamos esperando el documento para un nuevo paciente
            interaction_data[user_id]['esperando_documento'] = True
            interaction_data[user_id]['es_nuevo_registro'] = True
            
            # Solicitar documento en el idioma seleccionado
            if idioma == 'es':
                mensaje = "Por favor, ingresa el número de documento de identidad para el nuevo paciente. Este dato se utiliza únicamente para llevar un registro de tus consultas médicas."
            else:
                mensaje = "Please enter the identification number for the new patient. This information is used only to keep track of your medical consultations."
            
            await query.message.reply_text(mensaje)
    
    except Exception as e:
        print(f"Error al manejar la selección de paciente: {str(e)}")
        if user_id in interaction_data:
            interaction_data[user_id]['error_details'] = str(e)
        await query.message.reply_text("Ocurrió un error. Por favor, intenta nuevamente con /start.")


async def handle_rating(update: Update, context):
    try:
        query = update.callback_query
        user_id = query.from_user.id
        callback_data = query.data
        idioma = user_data[user_id]['idioma']
        sesion_id = interaction_data[user_id].get("sesion_id")

        # Extraer calificación
        rating = int(callback_data.split('_')[1])
        interaction_data[user_id]['calificacion'] = rating
        print(f"[RATING] Usuario {user_id} calificó con {rating} estrellas")

        # Calcular tiempo de sesión y marcar como finalizada
        fecha_fin = datetime.now()
        interaction_data[user_id]['fecha_fin'] = fecha_fin

        supabase.table("sesiones").update({
            "calificacion": rating,
            "fecha_fin": fecha_fin.isoformat(),
            "estado": "finalizada"
        }).eq("id", sesion_id).execute()

        # Mensaje de agradecimiento
        await query.message.reply_text(obtener_respuesta(idioma, 'gracias'))

        # Limpiar datos de memoria
        user_data.pop(user_id, None)
        interaction_data.pop(user_id, None)

    except Exception as e:
        print(f"Error al manejar la calificación: {str(e)}")
        await query.message.reply_text("Error al procesar tu calificación.")



def main():
    token = os.getenv('TELEGRAM_TOKEN')
    app = Application.builder().token(token).build()

    print("Bot iniciado. Presiona Ctrl+C para detenerlo.")

# Añadir manejadores
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(set_language, pattern='^(lang_es|lang_en|lang_es_nuevo|lang_en_nuevo|lang_es_existing|lang_en_existing)$'))
    app.add_handler(CallbackQueryHandler(handle_historial, pattern='^(historial_|nueva_consulta)'))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.add_handler(CallbackQueryHandler(handle_confirmation, pattern='^(confirm_yes|confirm_no)$'))
    app.add_handler(CallbackQueryHandler(handle_satisfaction, pattern='^(satisfied_yes|satisfied_no)$'))
    app.add_handler(CallbackQueryHandler(handle_correction, pattern='^(corregir_|finalizar_correccion)'))
    app.add_handler(CallbackQueryHandler(handle_rating, pattern='^rating_[1-5]$'))


        # Iniciar el bot con polling en lugar de webhook
    app.run_polling()

if __name__ == "__main__":
    main()