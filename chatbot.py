from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes
import snowflake.connector
import json
import asyncio
from datetime import datetime
from translations import translations  # Importar las traducciones

# Diccionario para almacenar las respuestas del usuario y datos de interacción
user_data = {}
inactive_users = {}  # Para rastrear usuarios inactivos
interaction_data = {}  # Para almacenar datos básicos de usuario

def obtener_respuesta(idioma, clave, **kwargs):
    if idioma in translations:
        return translations[idioma].get(clave, "Lo siento, no entiendo tu mensaje.").format(**kwargs)
    else:
        return "Sorry, I can't detect your language."

from dotenv import load_dotenv
import os

load_dotenv()  # Carga las variables del archivo .env

def save_interaction_data(data):
    try:
        conn = snowflake.connector.connect(
            user=os.getenv('SNOWFLAKE_USER'),
            password=os.getenv('SNOWFLAKE_PASSWORD'),
            account=os.getenv('SNOWFLAKE_ACCOUNT'),
            warehouse=os.getenv('SNOWFLAKE_WAREHOUSE'),
            database=os.getenv('SNOWFLAKE_DATABASE'),
            schema=os.getenv('SNOWFLAKE_SCHEMA')
        )
        cursor = conn.cursor()
        
        query = """
            INSERT INTO bot_interactions (
                user_id, chat_id, interaction_start, interaction_end, 
                symptoms_reported, diagnosis_provided, confirmation_status, 
                satisfaction_status, messages_exchanged, session_duration_seconds, 
                inactivity_flag, error_details
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s);
        """
        cursor.execute(query, (
            data['user_id'], data['chat_id'], 
            data['start_time'], data.get('end_time', None), 
            data.get('symptoms_reported', None), data.get('diagnosis_provided', None),
            data.get('confirmation_status', None), data.get('satisfaction_status', None),
            data.get('messages_exchanged', 0), data.get('session_duration_seconds', 0),
            data.get('inactivity_flag', None), data.get('error_details', None)
        ))
        
        conn.commit()
        cursor.close()
        conn.close()
    except Exception as e:
        print(f"Error al guardar datos en Snowflake: {e}")

# Conexión con Snowflake
def get_diagnosis(sintomas, idioma):
    try:
        conn = snowflake.connector.connect(
            user=os.getenv('SNOWFLAKE_USER'),
            password=os.getenv('SNOWFLAKE_PASSWORD'),
            account=os.getenv('SNOWFLAKE_ACCOUNT'),
            warehouse=os.getenv('SNOWFLAKE_WAREHOUSE'),
            database=os.getenv('SNOWFLAKE_DATABASE'),
            schema=os.getenv('SNOWFLAKE_SCHEMA')
        )
        cursor = conn.cursor()

        prompt = f"El usuario reporta los siguientes síntomas: {sintomas}. Devuelve: 1. Posibles diagnósticos preliminares. 2. Tratamientos caseros. 3. Cuándo debe buscar atención médica."
        if idioma == 'en':
            prompt = f"The user reports the following symptoms: {sintomas}. Return: 1. Possible preliminary diagnoses. 2. Home treatments. 3. When to seek medical attention."
        print(prompt)
        messages = [{"role": "user", "content": prompt}]
        messages_json = json.dumps(messages)
        escaped_json = messages_json.replace('"', '\\"')

        query = f"""
            SELECT SNOWFLAKE.CORTEX.COMPLETE(
                'mistral-large2',
                PARSE_JSON('{escaped_json}')
            );
        """
        cursor.execute(query)
        result = cursor.fetchone()
        cursor.close()
        conn.close()
        return result[0] if result else "No se encontró un diagnóstico para estos síntomas."
    except Exception as e:
        return f"Error al obtener diagnóstico: {str(e)}"

# Función para el comando /start o mensajes de saludo
async def start(update: Update, context):
    try:
        user_id = update.effective_user.id
        user_name = update.effective_user.username or "Desconocido"
        chat_id = update.effective_chat.id
        timestamp = update.message.date
        
        # Guardar datos básicos del usuario
        interaction_data[user_id] = {
            'user_id': user_id,
            'user_name': user_name,
            'chat_id': chat_id,
            'start_time': timestamp
        }
      
        # Registrar el tiempo de inicio de la sesión
        user_data[user_id] = {'sintomas': [], 'start_time': datetime.now()}

        # Mostrar los datos básicos del usuario en consola
        print(f"[INICIO] ID={user_id}, Usuario={user_name}, Chat={chat_id}, Timestamp={timestamp}")

        # Mostrar opciones de idioma
        keyboard = [
            [InlineKeyboardButton("Español", callback_data="lang_es")],
            [InlineKeyboardButton("English", callback_data="lang_en")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text("Please select your language / Por favor, selecciona tu idioma:", reply_markup=reply_markup)
    except Exception as e:
        print(f"Error al iniciar la conversación: {str(e)}")
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
            user_data.pop(user_id, None)
            interaction_data.pop(user_id, None)  # Eliminar datos de interacción
            await context.bot.send_message(chat_id=user_id, text=obtener_respuesta('es', 'inactividad'))
    except Exception as e:
        print(f"Error en la función de inactividad: {str(e)}")

# Función para manejar mensajes de texto
async def handle_message(update: Update, context):
    try:
        user_id = update.effective_user.id
        user_response = update.message.text.lower()
        timestamp = update.message.date  # Para registrar el tiempo de la respuesta

        if user_id not in user_data:
            await start(update, context)
            return

        # Registrar y actualizar síntomas
        idioma = user_data[user_id]['idioma']
        user_data[user_id]['sintomas'].append(user_response)

        # Guardar los síntomas reportados en interaction_data
        interaction_data[user_id]['symptoms_reported'] = ", ".join(user_data[user_id]['sintomas'])
        print(f"[ACTUALIZADO] Usuario={user_id}, Síntomas={interaction_data[user_id]['symptoms_reported']}")

        if len(user_data[user_id]['sintomas']) == 1:
            await update.message.reply_text(obtener_respuesta(idioma, 'pregunta_sintomas_1'), parse_mode='Markdown')
        elif len(user_data[user_id]['sintomas']) == 2:
            await update.message.reply_text(obtener_respuesta(idioma, 'pregunta_sintomas_2'), parse_mode='Markdown')
        elif len(user_data[user_id]['sintomas']) == 3:
            await update.message.reply_text(obtener_respuesta(idioma, 'pregunta_sintomas_3'))
        elif len(user_data[user_id]['sintomas']) == 4:
            await update.message.reply_text(obtener_respuesta(idioma, 'pregunta_sintomas_4'))
        elif len(user_data[user_id]['sintomas']) == 5:
            await update.message.reply_text(obtener_respuesta(idioma, 'pregunta_sintomas_5'))
        elif len(user_data[user_id]['sintomas']) == 6:
            await update.message.reply_text(obtener_respuesta(idioma, 'pregunta_sintomas_6'))
        elif len(user_data[user_id]['sintomas']) == 7:
            # Crear información de síntomas
            sintomas_info = {
                obtener_respuesta(idioma, 'descripcion_sintomas'): user_data[user_id]['sintomas'][0],
                obtener_respuesta(idioma, 'duracion_sintomas'): user_data[user_id]['sintomas'][1],
                obtener_respuesta(idioma, 'intensidad_sintomas'): user_data[user_id]['sintomas'][2],
                obtener_respuesta(idioma, 'frecuencia_sintomas'): user_data[user_id]['sintomas'][3],
                obtener_respuesta(idioma, 'cambios_sintomas'): user_data[user_id]['sintomas'][4],
                obtener_respuesta(idioma, 'datos_relevantes'): user_data[user_id]['sintomas'][5],
                obtener_respuesta(idioma, 'antecedentes_medicos'): user_data[user_id]['sintomas'][6]
            }

            # Crear texto formateado en HTML
            sintomas_text = "\n".join(
                [f"<b>{key}</b>: {value}" for key, value in sintomas_info.items()]
            )
            user_data[user_id]['sintomas_info'] = sintomas_info

            # Crear teclado
            keyboard = [
                [InlineKeyboardButton(obtener_respuesta(idioma, 'confirm_yes'), callback_data="confirm_yes")],
                [InlineKeyboardButton(obtener_respuesta(idioma, 'confirm_no'), callback_data="confirm_no")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)

            # Enviar mensaje con formato HTML
            await update.message.reply_text(
                obtener_respuesta(idioma, 'confirmacion_sintomas', sintomas_text=sintomas_text),
                reply_markup=reply_markup,
                parse_mode="HTML"
            )
    except Exception as e:
        print(f"Error al manejar el mensaje del usuario: {str(e)}")
        await update.message.reply_text(obtener_respuesta('es', 'error_mensaje'))

async def handle_confirmation(update: Update, context):
    try:
        query = update.callback_query
        user_id = query.from_user.id

        # Verificar si 'start_time' está presente antes de acceder a él
        if user_id not in user_data or 'start_time' not in user_data[user_id]:
            await query.message.reply_text("Parece que la sesión ha expirado. Usa /start para reiniciar.")
            return

        idioma = user_data[user_id]['idioma']
        sintomas_info = user_data[user_id].get('sintomas_info', {})

        # Calcular la duración de la sesión
        start_time = user_data[user_id]['start_time']
        end_time = datetime.now()
        session_duration = (end_time - start_time).total_seconds()  # En segundos

        # Registrar la duración de la sesión
        interaction_data[user_id]['session_duration_seconds'] = session_duration
        interaction_data[user_id]['end_time'] = end_time
        print(f"[FIN] Usuario {user_id} - Duración de la sesión: {session_duration} segundos")

        # Informar al usuario que el diagnóstico está en proceso
        await query.message.reply_text(obtener_respuesta(idioma, 'diagnostico_proceso'))

        # Agregar el diagnóstico al final
        diagnostico = get_diagnosis(json.dumps(sintomas_info), idioma)
        interaction_data[user_id]['diagnosis_provided'] = diagnostico

        # Enviar el diagnóstico al usuario
        await query.message.reply_text(obtener_respuesta(idioma, 'diagnostico', diagnostico=diagnostico))


        # Preguntar si está satisfecho
        keyboard = [
            [InlineKeyboardButton(obtener_respuesta(idioma, 'confirm_yes'), callback_data="satisfied_yes")],
            [InlineKeyboardButton(obtener_respuesta(idioma, 'confirm_no'), callback_data="satisfied_no")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.message.reply_text(obtener_respuesta(idioma, 'satisfaccion'), reply_markup=reply_markup)
    except Exception as e:
        print(f"Error al manejar la confirmación del usuario: {str(e)}")
        await query.message.reply_text(obtener_respuesta('es', 'error_confirmacion'))

# Manejar satisfacción del usuario
async def handle_satisfaction(update: Update, context):
    try:
        query = update.callback_query
        user_id = query.from_user.id

        if query.data == "satisfied_yes":
            interaction_data[user_id]['satisfaction_status'] = "Sí"
            await query.message.reply_text(obtener_respuesta('es', 'gracias'))
        elif query.data == "satisfied_no":
            interaction_data[user_id]['satisfaction_status'] = "No"
            await query.message.reply_text(obtener_respuesta('es', 'disculpa'))

        # Llamar a la función para guardar los datos al final de la interacción
        save_interaction_data(interaction_data[user_id])
        
        print(f"Satisfaction status antes de guardar: {interaction_data[user_id].get('satisfaction_status')}")
        # Limpiar datos y apagar el bot para este usuario
        user_data.pop(user_id, None)
        interaction_data.pop(user_id, None)
    except Exception as e:
        print(f"Error al manejar la satisfacción del usuario: {str(e)}")
        await query.message.reply_text(obtener_respuesta('es', 'error_satisfaccion'))

# Crear y añadir manejadores de comandos
def main():
    token=os.getenv('TELEGRAM_TOKEN')
    application = Application.builder().token(token).build()

    # Comandos y mensajes
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(set_language, pattern='^(lang_es|lang_en)$'))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    application.add_handler(CallbackQueryHandler(handle_confirmation, pattern='^(confirm_yes|confirm_no)$'))
    application.add_handler(CallbackQueryHandler(handle_satisfaction, pattern='^(satisfied_yes|satisfied_no)$'))

    application.run_polling()

if __name__ == "__main__":
    main()