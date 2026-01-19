import logging
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, CallbackQueryHandler, filters, Application
from config.settings import BOT_TOKEN, LOG_LEVEL
from services.database_service import init_db
# Importamos toggle_chat_mode para el comando /chat
from core.handlers.menu_handler import (
    start_menu, button_callback, handle_incoming_photo,
    handle_text_message, toggle_chat_mode, handle_new_member
)
from core.handlers.captcha_handler import verify_callback
from core.handlers.admin_handler import ban_command, mute_command, unmute_command, purge_command, unlock_command

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO if LOG_LEVEL == "INFO" else logging.DEBUG
)
logger = logging.getLogger(__name__)

async def post_init(application: Application):
    logger.info("⚙️ Iniciando servicios de Velzar...")
    await init_db()
    logger.info("✅ Base de datos conectada.")

def main():
    if not BOT_TOKEN: return

    app = ApplicationBuilder().token(BOT_TOKEN).post_init(post_init).build()

    # Comandos
    app.add_handler(CommandHandler("start", start_menu))
    app.add_handler(CommandHandler("chat", toggle_chat_mode)) # /chat activa DeepSeek

    # Comandos Admin
    app.add_handler(CommandHandler("ban", ban_command))
    app.add_handler(CommandHandler("mute", mute_command))
    app.add_handler(CommandHandler("unmute", unmute_command))
    app.add_handler(CommandHandler("purge", purge_command))
    app.add_handler(CommandHandler("unlock", unlock_command))

    # Mensajes
    app.add_handler(MessageHandler(filters.PHOTO, handle_incoming_photo))
    # Anti-Raid Monitor (Nuevos miembros)
    app.add_handler(MessageHandler(filters.StatusUpdate.NEW_CHAT_MEMBERS, handle_new_member))
    # Manejamos TODO el texto con una sola función inteligente
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text_message))

    # Botones
    app.add_handler(CallbackQueryHandler(button_callback, pattern="^(main|toggle|gen|upload|profile|edit).*"))
    # Boton Captcha (regex distinct)
    app.add_handler(CallbackQueryHandler(verify_callback, pattern="^verify_"))

    logger.info("🚀 Velzar v2.2 (Alpha Text) Online.")
    app.run_polling()

if __name__ == '__main__':
    main()