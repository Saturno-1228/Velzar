import logging
from telegram.ext import ApplicationBuilder, Application
from config.settings import BOT_TOKEN, LOG_LEVEL
from services.database_service import init_db
# Import Security Service (to be used later)
# from core.security_service import SecurityService

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO if LOG_LEVEL == "INFO" else logging.DEBUG
)
logger = logging.getLogger(__name__)

async def post_init(application: Application):
    logger.info("⚙️ Starting Velzar Services...")
    await init_db()

    # --- HERE GOES SECURITY SERVICE INITIALIZATION ---
    # security_service = SecurityService()
    # application.bot_data["security"] = security_service

    # Pre-fetch bot info
    me = await application.bot.get_me()
    application.bot_data["username"] = me.username
    logger.info(f"✅ Database loaded. Identity confirmed: @{me.username}")

def main():
    if not BOT_TOKEN:
        logger.error("❌ BOT_TOKEN not found in environment variables.")
        return

    app = ApplicationBuilder().token(BOT_TOKEN).post_init(post_init).build()

    # --- HERE GO HANDLERS ---
    # app.add_handler(CommandHandler("start", start_menu))
    # app.add_handler(CommandHandler("ban", ban_command))

    # --- HERE GOES SECURITY MIDDLEWARE (MessageHandler) ---

    logger.info("🚀 Velzar Security Bot (Clean Slate) Online.")
    app.run_polling()

if __name__ == '__main__':
    main()
