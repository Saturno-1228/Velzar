import logging
import asyncio
from telegram import Update, ChatPermissions
from telegram.ext import ContextTypes
from services.database_service import (
    add_ban_log, update_chat_log_channel, update_welcome_message
)
from config.settings import ADMIN_USER_ID

logger = logging.getLogger(__name__)

# --- UTILIDADES ---

async def _get_target_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Extrae el usuario objetivo de una respuesta o argumento."""
    if update.message.reply_to_message:
        return update.message.reply_to_message.from_user

    if context.args:
        try:
            user_id = int(context.args[0])
            return await context.bot.get_chat_member(update.effective_chat.id, user_id).user
        except (ValueError, Exception):
            return None
    return None

async def _check_admin(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """Verifica si el usuario es administrador."""
    user = update.effective_user
    chat = update.effective_chat

    # Dueño supremo
    if user.id == int(ADMIN_USER_ID):
        return True

    try:
        member = await chat.get_chat_member(user.id)
        return member.status in ["creator", "administrator"]
    except Exception:
        return False

# --- COMANDOS PUNITIVOS ---

async def ban_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Banea a un usuario manualmente."""
    if not await _check_admin(update, context):
        return

    target = await _get_target_user(update, context)
    if not target:
        await update.message.reply_text("❌ Responde a un mensaje o dame un ID.")
        return

    try:
        await update.effective_chat.ban_member(target.id)
        await update.message.reply_text(f"🔨 **Banned:** {target.mention_html()}", parse_mode="HTML")
        # Log (bot_id=0 para acciones manuales o id del admin)
        await add_ban_log(target.id, update.effective_chat.id, "Manual Ban", update.effective_user.id)
    except Exception as e:
        await update.message.reply_text(f"❌ Error: {e}")

async def mute_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Silencia a un usuario manualmente."""
    if not await _check_admin(update, context):
        return

    target = await _get_target_user(update, context)
    if not target:
        await update.message.reply_text("❌ Responde a un mensaje o dame un ID.")
        return

    try:
        permissions = ChatPermissions(can_send_messages=False)
        await update.effective_chat.restrict_member(target.id, permissions)
        await update.message.reply_text(f"🤐 **Muted:** {target.mention_html()}", parse_mode="HTML")
        await add_ban_log(target.id, update.effective_chat.id, "Manual Mute", update.effective_user.id)
    except Exception as e:
        await update.message.reply_text(f"❌ Error: {e}")

async def purge_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Borra mensajes masivamente."""
    if not await _check_admin(update, context):
        return

    try:
        count = int(context.args[0]) if context.args else 10
        message_id = update.message.message_id

        # Generar lista de IDs a borrar (hacia atrás)
        # Nota: delete_messages es más eficiente si se tiene la lista, pero message_ids son secuenciales aprox.
        # Telegram API permite borrar lista. Haremos un loop simple o delete_message en batch si soportado (python-telegram-bot v20+ tiene delete_messages)

        # Estrategia simple: borrar el comando y N anteriores
        await update.message.delete()

        # Esto es aproximado, lo ideal es borrar por reply hasta el final
        # Pero para purge simple:
        deleted_count = 0
        current_id = message_id - 1
        for _ in range(count):
            try:
                await context.bot.delete_message(update.effective_chat.id, current_id)
                deleted_count += 1
            except Exception:
                pass # Mensaje no existe o no se puede borrar
            current_id -= 1

        msg = await context.bot.send_message(update.effective_chat.id, f"🗑️ Se barrieron {deleted_count} mensajes.")
        await asyncio.sleep(3)
        await msg.delete()

    except Exception as e:
        await context.bot.send_message(update.effective_chat.id, f"❌ Error en purge: {e}")

# --- COMANDOS DE CONFIGURACIÓN ---

async def setlog_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Configura el canal de logs."""
    if not await _check_admin(update, context):
        return

    # Si se ejecuta en un canal, usar ese ID
    if update.effective_chat.type == "channel":
        channel_id = update.effective_chat.id
        # Necesitamos el ID del grupo asociado o pasar el ID del canal en el grupo
        # Este comando es tricky. Mejor: "/setlog <channel_id>" en el grupo, o "/setlog" en el grupo y pasar el ID.
        # Vamos a asumir uso en grupo pasando ID
        pass

    if not context.args:
        await update.message.reply_text("Uso: /setlog <channel_id> (Ej: -100123456789)")
        return

    try:
        log_channel_id = int(context.args[0])
        await update_chat_log_channel(update.effective_chat.id, log_channel_id)

        # Enviar mensaje de prueba al canal
        try:
            await context.bot.send_message(log_channel_id, "✅ Velzar Logs conectados correctamente.")
            await update.message.reply_text("✅ Canal de logs configurado.")
        except Exception:
            await update.message.reply_text("⚠️ Guardado, pero no pude enviar mensaje al canal. ¿Soy admin allí?")

    except ValueError:
        await update.message.reply_text("ID inválido.")

async def setwelcome_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Configura el mensaje de bienvenida."""
    if not await _check_admin(update, context):
        return

    if not context.args:
        await update.message.reply_text("Uso: /setwelcome <texto>. Usa {name} y {chat_title}.")
        return

    welcome_text = " ".join(context.args)
    await update_welcome_message(update.effective_chat.id, welcome_text, enabled=True)
    await update.message.reply_text("✅ Mensaje de bienvenida actualizado.")

# --- COMANDOS DE AUDITORÍA ---

async def check_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Auditoría manual por IA."""
    if not await _check_admin(update, context):
        return

    if not update.message.reply_to_message or not update.message.reply_to_message.text:
        await update.message.reply_text("❌ Responde a un mensaje de texto para auditarlo.")
        return

    text_to_check = update.message.reply_to_message.text
    msg = await update.message.reply_text("🧠 Analizando con Venice AI...")

    try:
        # Acceder al servicio de seguridad (inyectado en main)
        security_service = context.bot_data.get("security")
        if not security_service:
            await msg.edit_text("❌ Error interno: Servicio de seguridad no disponible.")
            return

        analysis = await security_service.venice.classify_message(text_to_check)

        risk = analysis.get("risk", "UNKNOWN")
        category = analysis.get("category", "UNKNOWN")
        reason = analysis.get("reason", "N/A")

        emoji = "🟢" if risk == "LOW" else "🟡" if risk == "MED" else "🔴"

        report = (
            f"🛡️ **Reporte de Auditoría**\n\n"
            f"Riesgo: {emoji} {risk}\n"
            f"Categoría: {category}\n"
            f"Razón: {reason}"
        )
        await msg.edit_text(report, parse_mode="Markdown")

    except Exception as e:
        await msg.edit_text(f"❌ Error durante el análisis: {e}")
