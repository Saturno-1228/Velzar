import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from services.database_service import get_or_create_user, get_chat_settings

logger = logging.getLogger(__name__)

# --- MANEJADOR DE COMANDO /START ---

async def start_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Maneja el comando /start mostrando el dashboard o estado."""
    user = update.effective_user
    chat = update.effective_chat

    # Asegurar que el usuario existe en DB
    await get_or_create_user(user.id, user.username)

    # 1. LÓGICA DE GRUPO
    if chat.type != "private":
        # Solo responder si es admin
        member = await chat.get_chat_member(user.id)
        if member.status in ["creator", "administrator"]:
            await update.message.reply_text("🛡️ **Velzar Active.** System Monitor: ON", parse_mode="Markdown")
        return

    # 2. LÓGICA PRIVADA (Dashboard)
    bot_username = context.bot.username
    # Link para añadir al grupo con permisos específicos
    add_group_url = f"https://t.me/{bot_username}?startgroup=true&admin=ban_users+restrict_members+delete_messages+pin_messages"

    text = (
        f"Hola, operador {user.first_name}.\n\n"
        "Soy **Velzar**, tu sistema de seguridad y auditoría avanzado.\n"
        "Opero bajo estrictos protocolos de eficiencia y protección.\n\n"
        "Selecciona una operación:"
    )

    keyboard = [
        [InlineKeyboardButton("➕ Añadir a un Grupo", url=add_group_url)],
        [InlineKeyboardButton("📚 Guía de Instalación", callback_data="guide_main")],
        [InlineKeyboardButton("⚙️ Mis Herramientas", callback_data="my_tools")],
        [InlineKeyboardButton("🆘 Soporte/Estado", callback_data="support")]
    ]

    await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

# --- MANEJADOR DE BOTONES (CALLBACKS) ---

async def menu_callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Maneja las interacciones con los botones del menú."""
    query = update.callback_query
    await query.answer()

    data = query.data
    user = query.from_user

    if data == "my_tools":
        # Obtener datos frescos
        db_user = await get_or_create_user(user.id, user.username)
        trust_score = db_user["trust_score"]
        credits = db_user["credits"]

        status_emoji = "🛡️" if trust_score >= 10 else "⚠️"

        text = (
            f"⚙️ **Tus Herramientas**\n\n"
            f"🆔 **ID:** `{user.id}`\n"
            f"{status_emoji} **Nivel de Confianza:** {trust_score}\n"
            f"🔋 **Créditos:** {credits}\n\n"
            "Tu reputación determina si la IA auditará tus mensajes."
        )
        keyboard = [[InlineKeyboardButton("🔙 Atrás", callback_data="back_home")]]
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

    elif data == "support":
        text = (
            "🆘 **Centro de Soporte**\n\n"
            "Estado del Sistema: 🟢 **ONLINE**\n"
            "Latencia IA: Baja\n\n"
            "¿Problemas? Contacta al canal oficial."
        )
        # Placeholder para canal oficial
        keyboard = [
            [InlineKeyboardButton("📢 Canal Oficial", url="https://t.me/telegram")],
            [InlineKeyboardButton("🔙 Atrás", callback_data="back_home")]
        ]
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

    elif data == "back_home":
        # Volver al inicio
        bot_username = context.bot.username
        add_group_url = f"https://t.me/{bot_username}?startgroup=true&admin=ban_users+restrict_members+delete_messages+pin_messages"

        text = (
            f"Hola, operador {user.first_name}.\n\n"
            "Soy **Velzar**, tu sistema de seguridad y auditoría avanzado.\n"
            "Selecciona una operación:"
        )
        keyboard = [
            [InlineKeyboardButton("➕ Añadir a un Grupo", url=add_group_url)],
            [InlineKeyboardButton("📚 Guía de Instalación", callback_data="guide_main")],
            [InlineKeyboardButton("⚙️ Mis Herramientas", callback_data="my_tools")],
            [InlineKeyboardButton("🆘 Soporte/Estado", callback_data="support")]
        ]
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

# --- MANEJADOR DE BIENVENIDA ---

async def welcome_new_member(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Da la bienvenida a nuevos miembros si está habilitado."""
    chat = update.effective_chat

    # Obtener configuración
    settings = await get_chat_settings(chat.id)
    if not settings or not settings["welcome_enabled"] or not settings["welcome_message"]:
        return

    welcome_template = settings["welcome_message"]

    for member in update.message.new_chat_members:
        if member.id == context.bot.id:
            # Mensaje de auto-presentación al ser añadido
            await context.bot.send_message(
                chat.id,
                "🛡️ **Sistema Velzar Integrado.**\n\nGracias por integrarme. Por favor, hazme **Administrador** ahora para activar mis escudos y protocolos de seguridad.",
                parse_mode="Markdown"
            )
            continue

        # Reemplazar placeholders
        text = welcome_template.replace("{name}", member.first_name).replace("{chat_title}", chat.title)
        await context.bot.send_message(chat.id, text)
