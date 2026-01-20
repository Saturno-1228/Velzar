import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

logger = logging.getLogger(__name__)

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Muestra el menú de ayuda categorizado.
    """
    text = (
        "🆘 **Centro de Ayuda Velzar**\n\n"
        "Selecciona una categoría para ver los comandos disponibles:"
    )

    buttons = [
        [InlineKeyboardButton("👮 Moderación", callback_data="help_mod")],
        [InlineKeyboardButton("⚙️ Configuración", callback_data="help_config")],
        [InlineKeyboardButton("🧠 IA & Auditoría", callback_data="help_ai")]
    ]

    await update.message.reply_text(
        text=text,
        reply_markup=InlineKeyboardMarkup(buttons),
        parse_mode="Markdown"
    )

async def help_callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Maneja la navegación del menú de ayuda.
    Patrón: ^help_
    """
    query = update.callback_query
    await query.answer()

    data = query.data
    text = ""
    buttons = []

    back_button = [InlineKeyboardButton("🔙 Volver al Menú", callback_data="help_main")]

    if data == "help_main":
        text = (
            "🆘 **Centro de Ayuda Velzar**\n\n"
            "Selecciona una categoría para ver los comandos disponibles:"
        )
        buttons = [
            [InlineKeyboardButton("👮 Moderación", callback_data="help_mod")],
            [InlineKeyboardButton("⚙️ Configuración", callback_data="help_config")],
            [InlineKeyboardButton("🧠 IA & Auditoría", callback_data="help_ai")]
        ]

    elif data == "help_mod":
        text = (
            "👮 **Comandos de Moderación**\n\n"
            "• `/ban` - Banear usuario (Responder mensaje)\n"
            "• `/mute` - Silenciar usuario (Responder mensaje)\n"
            "• `/unban` - Desbanear (Responder o ID)\n"
            "• `/unmute` - Quitar silencio (Responder)\n"
            "• `/warn` - Advertir usuario (+1 Warn)\n"
            "• `/purge [N]` - Borrar N mensajes masivamente"
        )
        buttons = [back_button]

    elif data == "help_config":
        text = (
            "⚙️ **Comandos de Configuración**\n\n"
            "• `/setlog [ID]` - Vincular canal de reportes/logs\n"
            "• `/setwelcome [Texto]` - Configurar mensaje de bienvenida"
        )
        buttons = [back_button]

    elif data == "help_ai":
        text = (
            "🧠 **Inteligencia Artificial & Auditoría**\n\n"
            "• `/check` - Auditoría Manual (Responder a mensaje sospechoso)\n"
            "• `/info` - Ver información detallada del usuario"
        )
        buttons = [back_button]

    await query.edit_message_text(
        text=text,
        reply_markup=InlineKeyboardMarkup(buttons),
        parse_mode="Markdown"
    )
