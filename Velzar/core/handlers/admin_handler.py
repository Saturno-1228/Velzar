from telegram import Update, ChatPermissions
from telegram.ext import ContextTypes
import datetime

# Helper para verificar admin
async def is_admin(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    user = update.effective_user
    chat = update.effective_chat
    if chat.type == "private": return True # En privado siempre es "admin" de su chat

    member = await context.bot.get_chat_member(chat.id, user.id)
    return member.status in ["administrator", "creator"]

async def ban_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_admin(update, context): return

    if not update.message.reply_to_message:
        await update.message.reply_text("⚠️ Responde al mensaje del usuario que quieres banear.")
        return

    user_to_ban = update.message.reply_to_message.from_user
    try:
        await context.bot.ban_chat_member(update.effective_chat.id, user_to_ban.id)
        await update.message.reply_text(f"🚫 **{user_to_ban.first_name}** ha sido baneado permanentemente.", parse_mode="Markdown")
    except Exception as e:
        await update.message.reply_text(f"❌ Error: {e}")

async def mute_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_admin(update, context): return

    if not update.message.reply_to_message:
        await update.message.reply_text("⚠️ Responde al mensaje del usuario.")
        return

    user_to_mute = update.message.reply_to_message.from_user
    # Mute por 1 hora por defecto
    until = datetime.datetime.now() + datetime.timedelta(hours=1)
    permissions = ChatPermissions(can_send_messages=False)

    try:
        await context.bot.restrict_chat_member(update.effective_chat.id, user_to_mute.id, permissions, until_date=until)
        await update.message.reply_text(f"🤫 **{user_to_mute.first_name}** silenciado por 1 hora.", parse_mode="Markdown")
    except Exception as e:
        await update.message.reply_text(f"❌ Error: {e}")

async def unmute_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_admin(update, context): return

    if not update.message.reply_to_message:
        await update.message.reply_text("⚠️ Responde al mensaje del usuario.")
        return

    user_to_unmute = update.message.reply_to_message.from_user
    permissions = ChatPermissions(
        can_send_messages=True,
        can_send_media_messages=True,
        can_send_other_messages=True,
        can_invite_users=True
    )

    try:
        await context.bot.restrict_chat_member(update.effective_chat.id, user_to_unmute.id, permissions)
        await update.message.reply_text(f"🔊 **{user_to_unmute.first_name}** ya puede hablar.", parse_mode="Markdown")
    except Exception as e:
        await update.message.reply_text(f"❌ Error: {e}")

async def purge_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Borra X mensajes. Uso: /purge 10"""
    if not await is_admin(update, context): return

    try:
        args = context.args
        limit = int(args[0]) if args else 10
        if limit > 100: limit = 100 # Seguridad Telegram

        message_id = update.message.message_id
        chat_id = update.effective_chat.id

        # Borrar hacia atrás
        deleted_count = 0
        for i in range(limit):
             try:
                 await context.bot.delete_message(chat_id, message_id - i)
                 deleted_count += 1
             except:
                 pass # Mensaje ya borrado o muy viejo

        confirmation = await context.bot.send_message(chat_id, f"🧹 **Limpieza completada:** {deleted_count} mensajes borrados.", parse_mode="Markdown")
        # Borrar confirmación a los 5s
        context.job_queue.run_once(lambda ctx: ctx.bot.delete_message(chat_id, confirmation.message_id), 5)

    except Exception as e:
        await update.message.reply_text(f"❌ Uso: `/purge [número]`")
