import logging
from telegram import (
    Update, BotCommand, BotCommandScopeAllPrivateChats,
    BotCommandScopeAllChatAdministrators
)
from telegram.ext import (
    ApplicationBuilder, Application, CommandHandler,
    CallbackQueryHandler, MessageHandler, filters, ContextTypes, ApplicationHandlerStop
)
from config.settings import BOT_TOKEN, LOG_LEVEL
from services.database_service import init_db
from core.security_service import SecurityService
from core.handlers.menu_handler import start_menu, menu_callback_handler, welcome_new_member
from core.handlers.admin_handler import (
    ban_command, mute_command, purge_command,
    setlog_command, setwelcome_command, check_command
)
from core.handlers.guide_handler import guide_callback_handler
from core.handlers.help_handler import help_command, help_callback_handler
from core.handlers.chat_handler import chat_reply_handler

# Configuración de Logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO if LOG_LEVEL == "INFO" else logging.DEBUG
)
logger = logging.getLogger(__name__)

# --- MIDDLEWARE DE SEGURIDAD ---

async def security_middleware(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Interceptor de tráfico. Ejecuta la lógica de seguridad antes que cualquier otro handler.
    Si el mensaje es bloqueado, detiene la propagación.
    """
    security_service = context.bot_data.get("security")
    if not security_service:
        return # Si el servicio no está listo, dejar pasar (fail open) o bloquear (fail close)

    # Ejecutar chequeo
    is_safe = await security_service.check_message(update, context)

    if not is_safe:
        # Si no es seguro (fue borrado/baneado), detener el procesamiento de otros handlers
        raise ApplicationHandlerStop

# --- INICIALIZACIÓN ---

async def post_init(application: Application):
    logger.info("⚙️ Iniciando Servicios de Velzar...")

    # 1. Base de Datos
    await init_db()

    # 2. Servicio de Seguridad (Motor Principal)
    security_service = SecurityService()
    application.bot_data["security"] = security_service
    logger.info("🛡️ Motor de Seguridad: ONLINE")

    # 3. Identidad del Bot
    me = await application.bot.get_me()
    application.bot_data["username"] = me.username
    logger.info(f"✅ Identidad confirmada: @{me.username}")

    # 4. Registrar Comandos Nativos (UX)
    # Scope: Usuarios (Privado)
    commands_private = [
        BotCommand("start", "Iniciar sistema"),
        BotCommand("help", "Ver menú de ayuda"),
    ]
    await application.bot.set_my_commands(commands_private, scope=BotCommandScopeAllPrivateChats())

    # Scope: Administradores (Grupos)
    commands_admin = [
        BotCommand("ban", "Banear usuario (Responder)"),
        BotCommand("mute", "Silenciar usuario (Responder)"),
        BotCommand("warn", "Advertir usuario"),
        BotCommand("unban", "Desbanear (ID o Respuesta)"),
        BotCommand("unmute", "Quitar silencio"),
        BotCommand("check", "Auditoría IA Manual"),
        BotCommand("purge", "Borrar mensajes (Ej: /purge 10)"),
        BotCommand("setlog", "Vincular canal de reportes"),
        BotCommand("setwelcome", "Configurar bienvenida"),
        BotCommand("info", "Ver info de usuario"),
    ]
    await application.bot.set_my_commands(commands_admin, scope=BotCommandScopeAllChatAdministrators())
    logger.info("📱 Menús nativos actualizados.")

def main():
    if not BOT_TOKEN:
        logger.error("❌ BOT_TOKEN no encontrado en variables de entorno.")
        return

    app = ApplicationBuilder().token(BOT_TOKEN).post_init(post_init).build()

    # --- REGISTRO DE HANDLERS ---

    # GRUPO -1: Seguridad (Prioridad Máxima)
    # Filtra textos y captions para análisis
    app.add_handler(MessageHandler(filters.TEXT | filters.CAPTION, security_middleware), group=-1)

    # GRUPO 0: Comandos y Lógica Principal

    # 1. Menús y UI
    app.add_handler(CommandHandler("start", start_menu))
    app.add_handler(CommandHandler("help", help_command))

    # Handlers específicos (pattern) ANTES del genérico
    app.add_handler(CallbackQueryHandler(guide_callback_handler, pattern="^guide_"))
    app.add_handler(CallbackQueryHandler(help_callback_handler, pattern="^help_"))
    app.add_handler(CallbackQueryHandler(menu_callback_handler))

    # 2. Administración y Configuración
    app.add_handler(CommandHandler("ban", ban_command))
    app.add_handler(CommandHandler("mute", mute_command))
    app.add_handler(CommandHandler("purge", purge_command))
    app.add_handler(CommandHandler("setlog", setlog_command))
    app.add_handler(CommandHandler("setwelcome", setwelcome_command))
    app.add_handler(CommandHandler("check", check_command)) # Auditoría Manual

    # 3. Bienvenidas (Eventos de Chat)
    app.add_handler(MessageHandler(filters.StatusUpdate.NEW_CHAT_MEMBERS, welcome_new_member))

    # 4. Chat Conversacional (Velzar Guardián)
    # Atrapa texto que no sea comando (Menciones y DMs se filtran dentro del handler)
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, chat_reply_handler))

    logger.info("🚀 Velzar Security Bot (Versión Comercial) Operativo.")
    app.run_polling()

if __name__ == '__main__':
    main()
