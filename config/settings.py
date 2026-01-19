import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///velzar.db")
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
ADMIN_USER_ID = int(os.getenv("ADMIN_USER_ID", "0"))
LOG_CHANNEL_ID = os.getenv("LOG_CHANNEL_ID") # Nuevo: Canal para reportes de seguridad

# Configuración Venice AI
VENICE_API_KEY = os.getenv("VENICE_API_KEY")
VENICE_API_BASE = "https://api.venice.ai/api/v1"

# Modelos
VENICE_IMG_MODEL = "venice-sd35"      # Default Imágenes
VENICE_EDIT_MODEL = "flux-dev"        # Default Edición
VENICE_TEXT_MODEL = "deepseek-v3.2"   # 🚀 MODELO ALPHA TEXTO (TEXT-TO-TEXT)
VENICE_FALLBACK_MODEL = "llama-3.3-70b" # 🛡️ MODELO DE RESPALDO (Plan B)