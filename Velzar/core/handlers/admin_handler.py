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

    # 3. Chat Privado (Ya NO da admin global, solo uso personal si no está restringido)
    # IMPORTANTE: Eliminamos el return True incondicional para evitar vulnerabilidad
    if chat.type == "private":
        # En privado pueden usar el bot, pero NO comandos de admin global como banlist
        # Esta función is_bot_admin se usa para comandos privilegiados.
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

# --- COMANDOS DE MODERACIÓN ---

async def ban_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_bot_admin(update, context): return

    if not update.message.reply_to_message:
        msg = await update.message.reply_text("⚠️ Responde al usuario.")
        context.job_queue.run_once(lambda ctx: ctx.bot.delete_message(update.effective_chat.id, msg.message_id), 5)
        await update.message.delete()
        return

    # EXIGIR RAZÓN
    reason = " ".join(context.args)
    if not reason:
        msg = await update.message.reply_text("⚠️ **ERROR:** Debes especificar un motivo.\nEj: `/ban @user Spam masivo`", parse_mode="Markdown")
        context.job_queue.run_once(lambda ctx: ctx.bot.delete_message(update.effective_chat.id, msg.message_id), 5)
        await update.message.delete()
        return

    user = update.message.reply_to_message.from_user
    admin_id = update.effective_user.id
    chat_id = update.effective_chat.id

    try:
        await context.bot.ban_chat_member(chat_id, user.id)
        # Log DB
        await add_ban_log(user.id, chat_id, reason, admin_id)

        # Stealth Delete Command
        await update.message.delete()

        # Public Announcement (Bot Style)
        await context.bot.send_message(
            chat_id,
            f"🚫 **SYSTEM BAN**\n👤 User: {user.first_name}\n📝 Reason: {reason}",
            parse_mode="Markdown"
        )
    except Exception as e:
        await update.message.reply_text(f"❌ Error: {e}")

async def unban_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_bot_admin(update, context): return

    # Soporte para reply o ID/Username
    user_id = None
    if update.message.reply_to_message:
        user_id = update.message.reply_to_message.from_user.id
    elif context.args:
        try:
            user_id = int(context.args[0])
        except:
            await update.message.reply_text("⚠️ ID inválido. Usa `/unban [ID]` o responde al usuario.")
            return

    if not user_id: return

    try:
        await context.bot.unban_chat_member(update.effective_chat.id, user_id, only_if_banned=True)
        # Log Update (Optional remove from DB or just Action)
        await remove_ban_log(user_id)

        await update.message.delete()
        msg = await update.message.reply_text(f"✅ Usuario {user_id} desbaneado.")
        context.job_queue.run_once(lambda ctx: ctx.bot.delete_message(update.effective_chat.id, msg.message_id), 5)
    except Exception as e:
        await update.message.reply_text(f"❌ Error: {e}")

async def banlist_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_bot_admin(update, context): return

    bans = await get_ban_list(10)
    if not bans:
        await update.message.reply_text("📭 Historial de baneos vacío.")
        return

    text = "📜 **ÚLTIMOS 10 BANEOS:**\n\n"
    for b in bans:
        text += f"🔹 **User:** `{b['user_id']}` | **Razón:** {b['reason']}\n"

    # Mensaje temporal (Stealth) - Solo admin lo ve (en grupo se borra rapido o se manda al privado si pudieramos)
    # Por ahora borramos a los 15s
    await update.message.delete()
    msg = await update.message.reply_text(text, parse_mode="Markdown")
    context.job_queue.run_once(lambda ctx: ctx.bot.delete_message(update.effective_chat.id, msg.message_id), 15)

# --- MUTE / UNMUTE / KICK / PIN / PURGE (Stealth Updates) ---
# Se actualizan para borrar el comando original y ser más discretos

async def mute_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_bot_admin(update, context): return
    if not update.message.reply_to_message: return

    user = update.message.reply_to_message.from_user
    until = datetime.datetime.now() + datetime.timedelta(hours=1)
    permissions = ChatPermissions(can_send_messages=False)

    try:
        await context.bot.restrict_chat_member(update.effective_chat.id, user.id, permissions, until_date=until)
        await update.message.delete()
        await update.message.reply_text(f"🤫 **{user.first_name}** silenciado (1h).", parse_mode="Markdown")
    except Exception: pass

async def unmute_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_bot_admin(update, context): return
    if not update.message.reply_to_message: return

    user = update.message.reply_to_message.from_user
    permissions = ChatPermissions(can_send_messages=True, can_send_media_messages=True, can_send_other_messages=True, can_invite_users=True)

    try:
        await context.bot.restrict_chat_member(update.effective_chat.id, user.id, permissions)
        await update.message.delete()
        await update.message.reply_text(f"🔊 **{user.first_name}** liberado.", parse_mode="Markdown")
    except Exception: pass

async def kick_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_bot_admin(update, context): return
    if not update.message.reply_to_message: return

    user = update.message.reply_to_message.from_user
    try:
        await context.bot.ban_chat_member(update.effective_chat.id, user.id)
        await context.bot.unban_chat_member(update.effective_chat.id, user.id)
        await update.message.delete()
        await update.message.reply_text(f"👢 **{user.first_name}** expulsado.", parse_mode="Markdown")
    except Exception: pass

async def pin_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_bot_admin(update, context): return
    if not update.message.reply_to_message: return
    try:
        await update.message.reply_to_message.pin(disable_notification=False)
        await update.message.delete()
    except Exception: pass

async def purge_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_bot_admin(update, context): return
    try:
        args = context.args
        limit = int(args[0]) if args else 10
        if limit > 100: limit = 100

        message_id = update.message.message_id
        chat_id = update.effective_chat.id
        await update.message.delete() # Borrar comando purge primero

        for i in range(limit):
             try: await context.bot.delete_message(chat_id, message_id - 1 - i)
             except: pass
    except Exception: pass

async def unlock_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    from core.handlers.menu_handler import security
    if not await is_bot_admin(update, context): return
    if security.lockdown_mode:
        security.lockdown_mode = False
        security.lockdown_end_time = 0
        await update.message.delete()
        msg = await update.message.reply_text("🔓 **Lockdown desactivado.**", parse_mode="Markdown")
        context.job_queue.run_once(lambda ctx: ctx.bot.delete_message(update.effective_chat.id, msg.message_id), 5)