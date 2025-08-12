-- 1. Tabla de usuarios
CREATE TABLE usuarios (
    id SERIAL PRIMARY KEY,
    chat_id BIGINT UNIQUE NOT NULL, -- ID de Telegram
    nombre TEXT,
    fecha_registro TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 2. Tabla de sesiones
CREATE TABLE sesiones (
    id SERIAL PRIMARY KEY,
    usuario_id INT REFERENCES usuarios(id) ON DELETE CASCADE,
    fecha_inicio TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    fecha_fin TIMESTAMP,
    estado TEXT DEFAULT 'activa', -- activa, finalizada, cancelada
    satisfaccion BOOLEAN,         -- TRUE si el usuario está satisfecho
    feedback_usuario TEXT,         -- Opinión escrita del usuario
    calificacion INT CHECK (calificacion BETWEEN 1 AND 5) -- 1 a 5 estrellas
);

-- 3. Tabla de consultas
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