from telegram import Update, ChatPermissions
from telegram.ext import ContextTypes
import datetime

# --- CONFIGURACIÓN DE ADMINS ---
# Lista en memoria de admins autorizados para usar el bot (además del Owner)
# En producción idealmente esto iría a BBDD, pero para eficiencia usamos set en memoria.
AUTHORIZED_BOT_ADMINS = set()

# Helper para verificar permisos de uso del BOT
async def is_bot_admin(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    user = update.effective_user
    chat = update.effective_chat

    # 1. El Owner (definido en settings) siempre es admin
    from config.settings import ADMIN_USER_ID
    if user.id == ADMIN_USER_ID:
        return True

    # 2. Admins autorizados manualmente por el Owner
    if user.id in AUTHORIZED_BOT_ADMINS:
        return True

    # 3. En chat privado, el usuario es su propio "admin" (para usar el bot personalmente)
    # A MENOS que queramos restringir el uso personal también, pero el requerimiento decía "en grupos".
    if chat.type == "private":
        return True

    return False

# --- GESTIÓN DE ADMINS (Solo Owner) ---
async def auth_admin_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Autoriza a un usuario para controlar a Velzar."""
    from config.settings import ADMIN_USER_ID
    if update.effective_user.id != ADMIN_USER_ID: return

    if not update.message.reply_to_message:
        await update.message.reply_text("⚠️ Responde al usuario que quieres autorizar.")
        return

    target_id = update.message.reply_to_message.from_user.id
    name = update.message.reply_to_message.from_user.first_name

    AUTHORIZED_BOT_ADMINS.add(target_id)
    await update.message.reply_text(f"✅ **{name}** ahora es Operador Autorizado de Velzar.")

async def unauth_admin_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Revoca autorización."""
    from config.settings import ADMIN_USER_ID
    if update.effective_user.id != ADMIN_USER_ID: return

    if not update.message.reply_to_message:
        return

    target_id = update.message.reply_to_message.from_user.id
    if target_id in AUTHORIZED_BOT_ADMINS:
        AUTHORIZED_BOT_ADMINS.remove(target_id)
        await update.message.reply_text(f"🚫 **Autorización revocada**.")

# --- COMANDOS DE MODERACIÓN (Requieren is_bot_admin) ---

async def ban_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_bot_admin(update, context): return

    if not update.message.reply_to_message:
        await update.message.reply_text("⚠️ Responde al usuario.")
        return

    user = update.message.reply_to_message.from_user
    try:
        await context.bot.ban_chat_member(update.effective_chat.id, user.id)
        await update.message.reply_text(f"🚫 **{user.first_name}** baneado.", parse_mode="Markdown")
    except Exception as e:
        await update.message.reply_text(f"❌ Error: {e}")

async def mute_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_bot_admin(update, context): return

    if not update.message.reply_to_message:
        await update.message.reply_text("⚠️ Responde al usuario.")
        return

    user = update.message.reply_to_message.from_user
    until = datetime.datetime.now() + datetime.timedelta(hours=1)
    permissions = ChatPermissions(can_send_messages=False)

    try:
        await context.bot.restrict_chat_member(update.effective_chat.id, user.id, permissions, until_date=until)
        await update.message.reply_text(f"🤫 **{user.first_name}** silenciado (1h).", parse_mode="Markdown")
    except Exception as e:
        await update.message.reply_text(f"❌ Error: {e}")

async def unmute_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_bot_admin(update, context): return

    if not update.message.reply_to_message:
        await update.message.reply_text("⚠️ Responde al usuario.")
        return

    user = update.message.reply_to_message.from_user
    permissions = ChatPermissions(
        can_send_messages=True, can_send_media_messages=True,
        can_send_other_messages=True, can_invite_users=True
    )

    try:
        await context.bot.restrict_chat_member(update.effective_chat.id, user.id, permissions)
        await update.message.reply_text(f"🔊 **{user.first_name}** liberado.", parse_mode="Markdown")
    except Exception as e:
        await update.message.reply_text(f"❌ Error: {e}")

async def kick_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Expulsa pero permite volver a entrar (Unban inmediato)"""
    if not await is_bot_admin(update, context): return

    if not update.message.reply_to_message:
        await update.message.reply_text("⚠️ Responde al usuario.")
        return

    user = update.message.reply_to_message.from_user
    chat_id = update.effective_chat.id
    try:
        await context.bot.ban_chat_member(chat_id, user.id)
        await context.bot.unban_chat_member(chat_id, user.id)
        await update.message.reply_text(f"👢 **{user.first_name}** expulsado (Kick).", parse_mode="Markdown")
    except Exception as e:
        await update.message.reply_text(f"❌ Error: {e}")

async def pin_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_bot_admin(update, context): return
    if not update.message.reply_to_message: return

    try:
        await update.message.reply_to_message.pin(disable_notification=False)
        await update.message.reply_text("📌 Mensaje fijado.")
    except Exception as e:
        await update.message.reply_text(f"❌ Error: {e}")

async def purge_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_bot_admin(update, context): return

    try:
        args = context.args
        limit = int(args[0]) if args else 10
        if limit > 100: limit = 100

        # Opción avanzada: /purge 10 @username (borrar solo de ese usuario)
        target_user_id = None
        if len(args) > 1 and args[1].startswith("@"):
             # Esto es complejo de resolver ID por username sin cache, simplificamos:
             # Solo soportamos reply para target purge por ahora o borrado general
             pass

        message_id = update.message.message_id
        chat_id = update.effective_chat.id

        deleted_count = 0
        for i in range(limit):
             try:
                 await context.bot.delete_message(chat_id, message_id - i)
                 deleted_count += 1
             except: pass

        confirmation = await context.bot.send_message(chat_id, f"🧹 **{deleted_count}** mensajes borrados.", parse_mode="Markdown")
        context.job_queue.run_once(lambda ctx: ctx.bot.delete_message(chat_id, confirmation.message_id), 3)

    except Exception:
        await update.message.reply_text("❌ Uso: `/purge [cant]`")

async def unlock_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    from core.handlers.menu_handler import security
    if not await is_bot_admin(update, context): return

    if security.lockdown_mode:
        security.lockdown_mode = False
        security.lockdown_end_time = 0
        await update.message.reply_text("🔓 **Lockdown desactivado.**", parse_mode="Markdown")
    else:
        await update.message.reply_text("ℹ️ Sistema normal.")
