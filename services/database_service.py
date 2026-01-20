import aiosqlite
import logging
import os
from config.settings import DATABASE_URL, ADMIN_USER_ID

logger = logging.getLogger(__name__)

# Extraer ruta limpia (remover sqlite:///)
DB_PATH = DATABASE_URL.replace("sqlite:///", "")

async def init_db():
    """Inicializa las tablas de la base de datos."""
    async with aiosqlite.connect(DB_PATH) as db:
        # Tabla de Usuarios (Identidad Básica y Reputación)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                trust_score INTEGER DEFAULT 0,
                credits INTEGER DEFAULT 0,
                joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Migración manual simple por si la tabla ya existía sin las columnas nuevas (solo para desarrollo)
        try:
            await db.execute("ALTER TABLE users ADD COLUMN trust_score INTEGER DEFAULT 0")
        except:
            pass
        try:
            await db.execute("ALTER TABLE users ADD COLUMN credits INTEGER DEFAULT 0")
        except:
            pass

        # Tabla de Baneos (Registros de Seguridad)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS bans (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                chat_id INTEGER,
                reason TEXT,
                admin_id INTEGER,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Tabla de Admins Autorizados (Persistencia)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS authorized_admins (
                user_id INTEGER PRIMARY KEY,
                added_by INTEGER,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Tabla de Configuración de Chat (Logs, Bienvenida)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS chat_settings (
                chat_id INTEGER PRIMARY KEY,
                log_channel_id INTEGER,
                welcome_message TEXT,
                welcome_enabled BOOLEAN DEFAULT 0
            )
        """)

        await db.commit()
        logger.info("✅ Base de datos inicializada.")

# --- GESTIÓN DE USUARIOS ---

async def get_or_create_user(user_id: int, username: str):
    """Obtiene un usuario o lo crea si es nuevo."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM users WHERE user_id = ?", (user_id,)) as cursor:
            user = await cursor.fetchone()

            if not user:
                await db.execute(
                    "INSERT INTO users (user_id, username, trust_score, credits) VALUES (?, ?, 0, 0)",
                    (user_id, username)
                )
                await db.commit()
                async with db.execute("SELECT * FROM users WHERE user_id = ?", (user_id,)) as cursor:
                    user = await cursor.fetchone()
            return user

async def get_user(user_id: int):
    """Obtiene datos de un usuario por ID."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM users WHERE user_id = ?", (user_id,)) as cursor:
            return await cursor.fetchone()

async def update_trust_score(user_id: int, increment: bool = True, reset: bool = False):
    """Actualiza el nivel de confianza (Trust Score) de un usuario."""
    async with aiosqlite.connect(DB_PATH) as db:
        if reset:
            await db.execute("UPDATE users SET trust_score = 0 WHERE user_id = ?", (user_id,))
        elif increment:
            # Tope máximo opcional, pero por ahora infinito
            await db.execute("UPDATE users SET trust_score = trust_score + 1 WHERE user_id = ?", (user_id,))
        else:
             # Decremento (no especificado en plan, pero útil)
             await db.execute("UPDATE users SET trust_score = MAX(0, trust_score - 1) WHERE user_id = ?", (user_id,))

        await db.commit()

# --- GESTIÓN DE CONFIGURACIÓN DE CHAT ---

async def get_chat_settings(chat_id: int):
    """Obtiene la configuración de un chat."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM chat_settings WHERE chat_id = ?", (chat_id,)) as cursor:
            return await cursor.fetchone()

async def update_chat_log_channel(chat_id: int, log_channel_id: int):
    """Establece el canal de logs para un grupo."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            INSERT INTO chat_settings (chat_id, log_channel_id) VALUES (?, ?)
            ON CONFLICT(chat_id) DO UPDATE SET log_channel_id = excluded.log_channel_id
        """, (chat_id, log_channel_id))
        await db.commit()

async def update_welcome_message(chat_id: int, message: str, enabled: bool = True):
    """Establece el mensaje de bienvenida."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            INSERT INTO chat_settings (chat_id, welcome_message, welcome_enabled) VALUES (?, ?, ?)
            ON CONFLICT(chat_id) DO UPDATE SET welcome_message = excluded.welcome_message, welcome_enabled = excluded.welcome_enabled
        """, (chat_id, message, enabled))
        await db.commit()

# --- SEGURIDAD Y BANEOS (Registro Velzar) ---

async def add_ban_log(user_id: int, chat_id: int, reason: str, admin_id: int):
    """Registra una acción de baneo."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO bans (user_id, chat_id, reason, admin_id) VALUES (?, ?, ?, ?)",
            (user_id, chat_id, reason, admin_id)
        )
        await db.commit()

async def get_ban_list(limit: int = 10):
    """Obtiene baneos recientes."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM bans ORDER BY timestamp DESC LIMIT ?", (limit,)) as cursor:
            return await cursor.fetchall()

# --- GESTIÓN DE ADMINS AUTORIZADOS ---

async def add_authorized_admin(user_id: int, added_by: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("INSERT OR IGNORE INTO authorized_admins (user_id, added_by) VALUES (?, ?)", (user_id, added_by))
        await db.commit()

async def remove_authorized_admin(user_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM authorized_admins WHERE user_id = ?", (user_id,))
        await db.commit()

async def get_authorized_admins():
    """Devuelve un conjunto de user_ids autorizados."""
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT user_id FROM authorized_admins") as cursor:
            rows = await cursor.fetchall()
            return {row[0] for row in rows}
