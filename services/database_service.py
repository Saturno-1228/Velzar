import aiosqlite
import logging
import os
from datetime import datetime
from config.settings import DATABASE_URL, ADMIN_USER_ID

logger = logging.getLogger(__name__)

# Extraemos la ruta limpia del archivo (quitamos sqlite:///)
DB_PATH = DATABASE_URL.replace("sqlite:///", "")

async def init_db():
    """Inicializa las tablas de usuarios y auditoría"""
    async with aiosqlite.connect(DB_PATH) as db:
        # Tabla de Usuarios (Simplified for security focus)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                reputation_score INTEGER DEFAULT 100,
                joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Tabla de Baneos
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

        # Tabla de Admins Autorizados (Persistence)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS authorized_admins (
                user_id INTEGER PRIMARY KEY,
                added_by INTEGER,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        await db.commit()
        logger.info("✅ Base de datos de seguridad lista.")

# --- GESTIÓN DE USUARIOS ---

async def get_or_create_user(user_id: int, username: str):
    """Obtiene un usuario o lo crea si es nuevo"""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM users WHERE user_id = ?", (user_id,)) as cursor:
            user = await cursor.fetchone()

            if not user:
                await db.execute(
                    "INSERT INTO users (user_id, username) VALUES (?, ?)",
                    (user_id, username)
                )
                await db.commit()
                async with db.execute("SELECT * FROM users WHERE user_id = ?", (user_id,)) as cursor:
                    user = await cursor.fetchone()
            return user

# --- SISTEMA DE BANEOS (Velzar Log) ---

async def add_ban_log(user_id: int, chat_id: int, reason: str, admin_id: int):
    """Registra un baneo en el historial"""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO bans (user_id, chat_id, reason, admin_id) VALUES (?, ?, ?, ?)",
            (user_id, chat_id, reason, admin_id)
        )
        await db.commit()

async def remove_ban_log(user_id: int):
    """(Opcional) Marca como desbaneado o borra el log más reciente"""
    pass

async def get_ban_list(limit: int = 10):
    """Obtiene los últimos baneos"""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM bans ORDER BY timestamp DESC LIMIT ?", (limit,)) as cursor:
            return await cursor.fetchall()

# --- GESTIÓN DE ADMINS AUTORIZADOS (Persistence) ---

async def add_authorized_admin(user_id: int, added_by: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("INSERT OR IGNORE INTO authorized_admins (user_id, added_by) VALUES (?, ?)", (user_id, added_by))
        await db.commit()

async def remove_authorized_admin(user_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM authorized_admins WHERE user_id = ?", (user_id,))
        await db.commit()

async def get_authorized_admins():
    """Devuelve un set de user_ids"""
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT user_id FROM authorized_admins") as cursor:
            rows = await cursor.fetchall()
            return {row[0] for row in rows}