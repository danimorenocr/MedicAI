from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes
import asyncio
from datetime import datetime
from translations import translations  # Importar las traducciones
from dotenv import load_dotenv
import os
from openai import OpenAI
from supabase import create_client

load_dotenv()  # Carga las variables del archivo .env

# Configuración
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

# Crear cliente
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

client = OpenAI(
    api_key=os.environ.get("OPENAI_API_KEY"),
)

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
inactive_users = {}  # Para rastrear usuarios inactivos
interaction_data = {}  # Para almacenar datos básicos de usuario

# --------------------------------------------------------------------------------------------------------------------------------

# Función para obtener o registrar un usuario
def registrar_usuario(chat_id, nombre):
    # Intentar buscar usuario
    res = supabase.table("usuarios").select("id").eq("chat_id", chat_id).execute()
    if res.data:
        return res.data[0]["id"]
    # Si no existe, crearlo
    nuevo = supabase.table("usuarios").insert({
        "chat_id": chat_id,
        "nombre": nombre
    }).execute()
    return nuevo.data[0]["id"]

# Función para crear sesión
def crear_sesion(usuario_id):
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

        # Guardar usuario en Supabase y obtener su id
        usuario_id = registrar_usuario(chat_id, user_name)

        # Crear nueva sesión y obtener sesion_id
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
            'sesion_id': sesion_id
        }
        user_data[user_id] = {'sintomas': [], 'start_time': datetime.now()}

        # Log en consola
        print(f"[INICIO] UsuarioID={usuario_id}, SesionID={sesion_id}, TelegramID={user_id}, Usuario={user_name}")

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

    if query.data == "lang_es":
        idioma = 'es'
    elif query.data == "lang_en":
        idioma = 'en'
    else:
        idioma = 'en'

    user_data[user_id]['idioma'] = idioma

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
        supabase.table("consultas").insert({
            "sesion_id": sesion_id,
            "tipo_mensaje": "pregunta_sintomas",
            "pregunta": pregunta,
            "respuesta_usuario": respuesta
        }).execute()            

# Función para manejar mensajes de texto
async def handle_message(update: Update, context):
    try:
        user_id = update.effective_user.id
        user_response = update.message.text.lower()
        timestamp = update.message.date  # Para registrar el tiempo de la respuesta

        if user_id not in user_data:
            await start(update, context)
            return
        
        # Incrementar contador de mensajes intercambiados
        if user_id in interaction_data:
            interaction_data[user_id]['messages_exchanged'] = interaction_data[user_id].get('messages_exchanged', 0) + 1
        
        # Verificar si estamos esperando una sugerencia
        if user_data[user_id].get('esperando_sugerencia', False):
            idioma = user_data[user_id]['idioma']
            
            # Guardar la sugerencia en interaction_data
            interaction_data[user_id]['user_feedback'] = user_response
            print(f"[FEEDBACK] Usuario {user_id} envió: {user_response}")
            
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
                obtener_respuesta(idioma, 'descripcion_sintomas'): user_data[user_id]['sintomas'][0],  # ¿Desde cuándo comenzaron estos síntomas?     
                obtener_respuesta(idioma, 'duracion_sintomas'): user_data[user_id]['sintomas'][1],  # ¿Desde cuándo comenzaron estos síntomas?
                obtener_respuesta(idioma, 'intensidad_sintomas'): user_data[user_id]['sintomas'][2],  # En escala de 1 a 10, ¿cómo calificarías tus síntomas?
                obtener_respuesta(idioma, 'frecuencia_sintomas'): user_data[user_id]['sintomas'][3],  # ¿Con qué frecuencia ocurren tus síntomas?
                obtener_respuesta(idioma, 'cambios_sintomas'): user_data[user_id]['sintomas'][4],  # ¿Has notado algún cambio reciente en tus síntomas?
                obtener_respuesta(idioma, 'datos_relevantes'): user_data[user_id]['sintomas'][5],  # ¿Hay algún otro dato relevante, como caídas o incidentes recientes?
                obtener_respuesta(idioma, 'antecedentes_medicos'): user_data[user_id]['sintomas'][6],  # ¿Tienes algún antecedente médico o enfermedad importante?
                obtener_respuesta(idioma, 'enfermedades_cronicas'): user_data[user_id]['sintomas'][7],  # ¿Presenta alguna enfermedad crónica?
                obtener_respuesta(idioma, 'alergias'): user_data[user_id]['sintomas'][8],  # Indique si es alérgico a algún medicamento o alimento.
                obtener_respuesta(idioma, 'edad'): user_data[user_id]['sintomas'][9],  # Indique su edad.
                obtener_respuesta(idioma, 'sexo'): user_data[user_id]['sintomas'][10],  # Indique su sexo (masculino, femenino).
                obtener_respuesta(idioma, 'peso'): user_data[user_id]['sintomas'][11],  # Indique su peso (kg).
                obtener_respuesta(idioma, 'altura'): user_data[user_id]['sintomas'][12]  # Indique su altura (cm).
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
        for pregunta, respuesta in sintomas_info.items():
            supabase.table("consultas").insert({
                "sesion_id": sesion_id,
                "tipo_mensaje": "pregunta_sintomas",
                "pregunta": pregunta,
                "respuesta_usuario": respuesta
            }).execute()

        print(f"[BD] {len(sintomas_info)} respuestas guardadas para sesión {sesion_id}")

        # Mensaje de espera
        espera_msg = obtener_respuesta(idioma, 'diagnostico_proceso')
        await query.message.reply_text(f"⏳ {espera_msg}")

        # Generar diagnóstico con ChatGPT
        sintomas_texto = "\n".join([f"{k}: {v}" for k, v in sintomas_info.items()])
        diagnostico = get_diagnosis(sintomas_texto, idioma)
        interaction_data[user_id]['diagnosis_provided'] = diagnostico

        # Guardar diagnóstico en la BD
        supabase.table("consultas").insert({
            "sesion_id": sesion_id,
            "tipo_mensaje": "diagnostico",
            "pregunta": "Diagnóstico generado",
            "respuesta_bot": diagnostico
        }).execute()

        print(f"[BD] Diagnóstico guardado para sesión {sesion_id}")

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


# Manejar feedback del usuario
async def handle_feedback(update: Update, context):
    try:
        user_id = update.effective_user.id
        user_response = update.message.text
        idioma = user_data[user_id]['idioma']
        sesion_id = interaction_data[user_id].get("sesion_id")

        # Guardar feedback en memoria
        interaction_data[user_id]['feedback_usuario'] = user_response
        print(f"[FEEDBACK] Usuario {user_id} envió: {user_response}")

        # Guardar en la BD
        supabase.table("sesiones").update({
            "feedback_usuario": user_response
        }).eq("id", sesion_id).execute()

        # Pedir calificación
        keyboard = [
            [
                InlineKeyboardButton("1 ⭐", callback_data="rating_1"),
                InlineKeyboardButton("2 ⭐⭐", callback_data="rating_2"),
                InlineKeyboardButton("3 ⭐⭐⭐", callback_data="rating_3"),
                InlineKeyboardButton("4 ⭐⭐⭐⭐", callback_data="rating_4"),
                InlineKeyboardButton("5 ⭐⭐⭐⭐⭐", callback_data="rating_5")
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text(obtener_respuesta(idioma, 'opinion'), reply_markup=reply_markup)

        user_data[user_id]['esperando_sugerencia'] = False

    except Exception as e:
        print(f"Error al manejar el feedback: {str(e)}")
        await update.message.reply_text(obtener_respuesta(idioma, 'error_feedback'))


# Manejar calificación del usuario y cerrar sesión
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
    app.add_handler(CallbackQueryHandler(set_language, pattern='^(lang_es|lang_en)$'))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.add_handler(CallbackQueryHandler(handle_confirmation, pattern='^(confirm_yes|confirm_no)$'))
    app.add_handler(CallbackQueryHandler(handle_satisfaction, pattern='^(satisfied_yes|satisfied_no)$'))
    app.add_handler(CallbackQueryHandler(handle_correction, pattern='^(corregir_|finalizar_correccion)'))
    app.add_handler(CallbackQueryHandler(handle_rating, pattern='^rating_[1-5]$'))


        # Iniciar el bot con polling en lugar de webhook
    app.run_polling()

if __name__ == "__main__":
    main()