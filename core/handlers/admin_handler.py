from telegram import Update, ChatPermissions
from telegram.ext import ContextTypes
import datetime
from services.database_service import (
    add_ban_log, remove_ban_log, get_ban_list,
    add_authorized_admin, remove_authorized_admin, get_authorized_admins
)

# --- CONFIGURACIÓN DE ADMINS ---
# Cache en memoria para evitar queries en cada mensaje
AUTHORIZED_BOT_ADMINS = set()

async def reload_authorized_admins():
    """Recarga la lista de admins desde la DB (Llamar al inicio)"""
    global AUTHORIZED_BOT_ADMINS
    AUTHORIZED_BOT_ADMINS = await get_authorized_admins()

# Helper para verificar permisos de uso del BOT
async def is_bot_admin(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    user = update.effective_user
    chat = update.effective_chat

    # 0. Owner Supremo
    from config.settings import ADMIN_USER_ID
    if user.id == ADMIN_USER_ID: return True

    # 1. Admin Autorizado (DB)
    if user.id in AUTHORIZED_BOT_ADMINS: return True

    # 2. Creador del Grupo (Usabilidad Fix)
    if chat.type in ["group", "supergroup"]:
        try:
            member = await context.bot.get_chat_member(chat.id, user.id)
            if member.status == "creator":
                return True
        except: pass

    # 3. Chat Privado
    if chat.type == "private":
        return False

    return False

# --- GESTIÓN DE ADMINS (Solo Owner) ---
async def auth_admin_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    from config.settings import ADMIN_USER_ID
    if update.effective_user.id != ADMIN_USER_ID: return
    if not update.message.reply_to_message: return

    target_id = update.message.reply_to_message.from_user.id

    # DB + Cache Update
    await add_authorized_admin(target_id, update.effective_user.id)
    AUTHORIZED_BOT_ADMINS.add(target_id)

    await update.message.delete()
    msg = await update.message.reply_text(f"✅ Operador Autorizado (Persistente).")
    context.job_queue.run_once(lambda ctx: ctx.bot.delete_message(update.effective_chat.id, msg.message_id), 3)

async def unauth_admin_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    from config.settings import ADMIN_USER_ID
    if update.effective_user.id != ADMIN_USER_ID: return
    if not update.message.reply_to_message: return

    target_id = update.message.reply_to_message.from_user.id

    # DB + Cache Update
    await remove_authorized_admin(target_id)
    if target_id in AUTHORIZED_BOT_ADMINS:
        AUTHORIZED_BOT_ADMINS.remove(target_id)

    await update.message.delete()
    msg = await update.message.reply_text(f"🚫 Revocado.")
    context.job_queue.run_once(lambda ctx: ctx.bot.delete_message(update.effective_chat.id, msg.message_id), 3)

# --- COMANDOS DE MODERACIÓN BÁSICOS ---
# Se conservan como base para la seguridad, pero se eliminarán del main loop por ahora para empezar limpio

async def ban_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_bot_admin(update, context): return
    # ... (Logic to be re-connected)

async def unban_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_bot_admin(update, context): return
    # ... (Logic to be re-connected)
