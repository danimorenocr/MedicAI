from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
from dotenv import load_dotenv
import os

# Cargar las variables de entorno desde el archivo .env
load_dotenv()

# Obtener el token del bot desde las variables de entorno
TOKEN = os.getenv('TELEGRAM_TOKEN')

# Función que se ejecuta al escribir /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text('¡Hola! Soy tu bot de prueba.')

# Crear la aplicación y agregar el handler
application = Application.builder().token(TOKEN).build()

# Agregar un handler para el comando /start
start_handler = CommandHandler('start', start)
application.add_handler(start_handler)

# Iniciar el bot
application.run_polling()
