# MedicAI - Chatbot Médico de Diagnóstico Preliminar

MedicAI es un chatbot de Telegram diseñado para proporcionar diagnósticos médicos preliminares basados en los síntomas reportados por los usuarios. El bot utiliza tecnología de IA (OpenAI) para analizar los síntomas y proporcionar orientación inicial, pero no reemplaza la consulta con un profesional de la salud.

## Características Principales

- **Multilingüe**: Soporte para español e inglés
- **Diagnósticos Preliminares**: Análisis de síntomas mediante IA
- **Historial de Consultas**: Los usuarios pueden acceder a consultas anteriores
- **Sistema de Retroalimentación**: Los usuarios pueden calificar y comentar sobre el diagnóstico
- **Almacenamiento de Datos**: Todas las consultas se guardan en una base de datos Supabase

## Flujo de Conversación

1. **Inicio y Verificación de Usuario**
   - El usuario inicia con `/start`
   - El sistema verifica si el usuario está registrado
   - Si es un usuario nuevo, se crea un registro y una nueva sesión
   - Si es un usuario existente, se verifica si tiene consultas previas

2. **Selección de Idioma**
   - El usuario selecciona entre español e inglés
   - Si el usuario tiene historial de consultas, se le muestra la opción de revisar consultas anteriores o iniciar una nueva

3. **Historial de Consultas (para usuarios existentes)**
   - Si el usuario elige ver su historial, se le muestran sus consultas previas con un resumen de los síntomas
   - El usuario puede seleccionar una consulta anterior para ver el diagnóstico o iniciar una nueva consulta

4. **Recopilación de Síntomas (para nuevas consultas)**
   - El bot solicita información sobre los síntomas
   - Pregunta sobre duración, intensidad y frecuencia de los síntomas
   - El usuario puede corregir las respuestas anteriores si es necesario

5. **Confirmación y Diagnóstico**
   - Se muestra un resumen de los síntomas para confirmación
   - Tras la confirmación, se genera un diagnóstico preliminar mediante IA
   - El diagnóstico incluye posibles causas, tratamientos caseros y cuándo buscar atención médica

6. **Retroalimentación**
   - El usuario evalúa la utilidad del diagnóstico (sí/no)
   - Puede proporcionar comentarios adicionales (feedback textual)
   - Califica la experiencia con estrellas (1-5)

7. **Cierre de Sesión**
   - Se agradece al usuario por usar el servicio
   - La sesión se marca como finalizada en la base de datos
   - Los datos del usuario se limpian de la memoria del bot

## Estructura de la Base de Datos

### 1. Tabla de usuarios
```sql
CREATE TABLE usuarios (
    id SERIAL PRIMARY KEY,
    chat_id BIGINT UNIQUE NOT NULL, -- ID de Telegram
    nombre TEXT,
    fecha_registro TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### 2. Tabla de sesiones
```sql
CREATE TABLE sesiones (
    id SERIAL PRIMARY KEY,
    usuario_id INT REFERENCES usuarios(id) ON DELETE CASCADE,
    fecha_inicio TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    fecha_fin TIMESTAMP,
    estado TEXT DEFAULT 'activa', -- activa, finalizada, cancelada
    satisfaccion BOOLEAN,         -- TRUE si el usuario está satisfecho
    feedback_usuario TEXT,        -- Opinión escrita del usuario
    calificacion INT CHECK (calificacion BETWEEN 1 AND 5) -- 1 a 5 estrellas
);
```

### 3. Tabla de consultas
```sql
CREATE TABLE consultas (
    id SERIAL PRIMARY KEY,
    sesion_id INT REFERENCES sesiones(id) ON DELETE CASCADE,
    tipo_mensaje TEXT, -- bienvenida, introduccion, diagnostico, pregunta_sintomas_1, etc.
    pregunta TEXT, -- Texto enviado por el bot
    respuesta_usuario TEXT, -- Texto del usuario
    respuesta_bot TEXT, -- Respuesta generada por ChatGPT
    error_detectado BOOLEAN DEFAULT FALSE, -- Si el pipeline detecta problema
    comentario_analisis TEXT, -- Observaciones de revisión
    fecha TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

## Requisitos

- Python 3.8+
- Telegram Bot Token
- Cuenta en OpenAI con clave API
- Cuenta en Supabase con clave API

## Configuración

1. Crea un archivo `.env` en la raíz del proyecto con:
```
TELEGRAM_TOKEN=tu_token_de_telegram
OPENAI_API_KEY=tu_clave_api_de_openai
SUPABASE_URL=tu_url_de_supabase
SUPABASE_KEY=tu_clave_de_supabase
```

2. Instala las dependencias:
```
pip install -r requirements.txt
```

3. Ejecuta el bot:
```
python chatbot.py
```

## Componentes Principales

- **chatbot.py**: Archivo principal con la lógica del bot
- **translations.py**: Contiene las traducciones para diferentes idiomas
- **dashboard.py**: Dashboard de análisis con Streamlit (opcional)

## Manejo de Errores

El bot incluye manejo de excepciones para asegurar la estabilidad:
- Errores de conexión con OpenAI o Supabase
- Errores en el procesamiento de mensajes
- Inactividad del usuario (cierre automático después de 30 minutos)

## Funciones Clave

- `verificar_sesiones_previas()`: Verifica si el usuario tiene consultas anteriores
- `obtener_resumen_sintomas()`: Recupera un resumen de los síntomas de consultas previas
- `obtener_diagnostico_sesion()`: Recupera el diagnóstico de una sesión específica
- `get_diagnosis()`: Genera un diagnóstico utilizando OpenAI
- `handle_historial()`: Maneja la navegación del historial de consultas del usuario

## Notas de Uso

- Este bot es para fines informativos y no sustituye la atención médica profesional
- Los diagnósticos son preliminares y generales
- La calidad del diagnóstico depende de la precisión de los síntomas proporcionados
- Se recomienda buscar atención médica para problemas de salud reales

---

Desarrollado por [danimorenocr](https://github.com/danimorenocr)
