import os
import aiohttp
import asyncio
from datetime import datetime

# Definimos la ruta donde se guardarán las evidencias
AUDIT_FOLDER = "audit_images"

def ensure_audit_folder_exists():
    """Crea la carpeta de auditoría si no existe"""
    if not os.path.exists(AUDIT_FOLDER):
        os.makedirs(AUDIT_FOLDER)
        print(f"📁 Carpeta '{AUDIT_FOLDER}' creada automáticamente.")

async def save_image_to_disk(image_data: bytes, user_id: int, prefix: str = "gen") -> str:
    """
    Guarda una imagen (bytes) en el disco duro para auditoría.
    
    Args:
        image_data: Los bytes de la imagen.
        user_id: El ID del usuario que generó/envió la imagen.
        prefix: 'in' (entrada), 'out' (salida/generada), 'mod' (modificada).
    
    Returns:
        str: La ruta del archivo guardado.
    """
    # Aseguramos que la carpeta exista (esto corre muy rápido)
    ensure_audit_folder_exists()
    
    # Generamos un nombre único: FECHA_HORA_USERID_TIPO.png
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{timestamp}_{user_id}_{prefix}.png"
    file_path = os.path.join(AUDIT_FOLDER, filename)
    
    # Escribimos el archivo en el disco (usamos un hilo aparte para no congelar el bot)
    await asyncio.to_thread(_write_file, file_path, image_data)
    
    return file_path

def _write_file(path, data):
    """Función auxiliar para escribir archivo (bloqueante)"""
    with open(path, "wb") as f:
        f.write(data)

async def download_telegram_file(file_id: str, bot_token: str) -> bytes:
    """Descarga una foto enviada por el usuario a Telegram"""
    # 1. Obtener la ruta del archivo en los servidores de Telegram
    async with aiohttp.ClientSession() as session:
        url_info = f"https://api.telegram.org/bot{bot_token}/getFile?file_id={file_id}"
        async with session.get(url_info) as resp:
            result = await resp.json()
            if not result.get("ok"):
                return None
            file_path = result["result"]["file_path"]
            
        # 2. Descargar el contenido real
        url_content = f"https://api.telegram.org/file/bot{bot_token}/{file_path}"
        async with session.get(url_content) as resp:
            if resp.status == 200:
                return await resp.read()
            return None