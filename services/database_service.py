import aiosqlite
import logging
import os
from config.settings import DATABASE_URL, ADMIN_USER_ID

logger = logging.getLogger(__name__)

# Extract clean path (remove sqlite:///)
DB_PATH = DATABASE_URL.replace("sqlite:///", "")

async def init_db():
    """Initializes database tables."""
    async with aiosqlite.connect(DB_PATH) as db:
        # User Table (Basic Identity)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Bans Table (Security Logs)
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

        # Authorized Admins Table (Persistence)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS authorized_admins (
                user_id INTEGER PRIMARY KEY,
                added_by INTEGER,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # --- HERE GOES NEW TABLES IF NEEDED ---

        await db.commit()
        logger.info("✅ Database initialized.")

# --- USER MANAGEMENT ---

async def get_or_create_user(user_id: int, username: str):
    """Gets a user or creates them if new."""
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

# --- SECURITY & BANS (Velzar Log) ---

async def add_ban_log(user_id: int, chat_id: int, reason: str, admin_id: int):
    """Logs a ban action."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO bans (user_id, chat_id, reason, admin_id) VALUES (?, ?, ?, ?)",
            (user_id, chat_id, reason, admin_id)
        )
        await db.commit()

async def remove_ban_log(user_id: int):
    """(Optional) Marks as unbanned or removes log."""
    pass # Implementation pending if needed

async def get_ban_list(limit: int = 10):
    """Gets recent bans."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM bans ORDER BY timestamp DESC LIMIT ?", (limit,)) as cursor:
            return await cursor.fetchall()

# --- AUTHORIZED ADMINS MANAGEMENT ---

async def add_authorized_admin(user_id: int, added_by: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("INSERT OR IGNORE INTO authorized_admins (user_id, added_by) VALUES (?, ?)", (user_id, added_by))
        await db.commit()

async def remove_authorized_admin(user_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM authorized_admins WHERE user_id = ?", (user_id,))
        await db.commit()

async def get_authorized_admins():
    """Returns a set of user_ids."""
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT user_id FROM authorized_admins") as cursor:
            rows = await cursor.fetchall()
            return {row[0] for row in rows}
