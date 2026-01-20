import logging
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, CallbackQueryHandler, filters, Application
from config.settings import BOT_TOKEN, LOG_LEVEL
from services.database_service import init_db
from core.handlers.admin_handler import reload_authorized_admins

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO if LOG_LEVEL == "INFO" else logging.DEBUG
)
logger = logging.getLogger(__name__)

async def post_init(application: Application):
    logger.info("⚙️ Iniciando servicios de Velzar...")
    await init_db()
    await reload_authorized_admins()

    # Pre-fetch bot info
    me = await application.bot.get_me()
    application.bot_data["username"] = me.username

    logger.info(f"✅ Base de datos cargada. Identidad confirmada: @{me.username}")

def main():
    if not BOT_TOKEN: return

    app = ApplicationBuilder().token(BOT_TOKEN).post_init(post_init).build()

    # TODO: Register Security Handlers here (Start, Help, Admin Commands)

    logger.info("🚀 Velzar Security Bot (Rebooted) Online.")
    app.run_polling()

if __name__ == '__main__':
    main()