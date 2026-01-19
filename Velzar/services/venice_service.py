import aiohttp
import base64
import logging
import asyncio
from config.settings import (
    VENICE_API_KEY, VENICE_API_BASE, VENICE_IMG_MODEL,
    VENICE_EDIT_MODEL, VENICE_TEXT_MODEL, VENICE_FALLBACK_MODEL
)

logger = logging.getLogger(__name__)

class VeniceService:
    def __init__(self):
        self.headers = {
            "Authorization": f"Bearer {VENICE_API_KEY}",
            "Content-Type": "application/json"
        }

    async def _post_request(self, endpoint, payload):
        url = f"{VENICE_API_BASE}/{endpoint}"
        timeout = aiohttp.ClientTimeout(total=300)

        async with aiohttp.ClientSession(timeout=timeout) as session:
            try:
                async with session.post(url, json=payload, headers=self.headers) as response:
                    if response.status == 200:
                        content_type = response.headers.get("Content-Type", "")
                        if "application/json" in content_type:
                            return await response.json()
                        else:
                            return await response.read()
                    else:
                        error_text = await response.text()
                        logger.error(f"Error Venice {response.status}: {error_text}")
                        return {"error": response.status, "details": error_text}
            except Exception as e:
                logger.error(f"Excepción: {e}")
                return None

    # --- CHAT CON FALLBACK (Self-Repair) ---
    async def generate_chat_reply(self, messages, max_tokens=1000, model=VENICE_TEXT_MODEL):
        """Conversa usando el modelo principal, con autoreparación (fallback) si falla."""
        payload = {
            "model": model,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": 0.7,
            "top_p": 0.9
        }

        logger.info(f"💬 Intentando chat con {model}...")
        data = await self._post_request("chat/completions", payload)

        # Validación de éxito
        if isinstance(data, dict) and "choices" in data:
            return data["choices"][0]["message"]["content"]

        # Lógica de Fallback (Autoreparación)
        if model == VENICE_TEXT_MODEL:
            logger.warning(f"⚠️ Fallo en modelo principal ({model}). Iniciando protocolo de autoreparación con {VENICE_FALLBACK_MODEL}...")
            return await self.generate_chat_reply(messages, max_tokens, model=VENICE_FALLBACK_MODEL)

        return None

    # --- GENERACIÓN DE IMÁGENES ---
    async def generate_image(self, prompt, model_id=None, negative_prompt="low quality, bad anatomy"):
        modelo_a_usar = model_id if model_id else VENICE_IMG_MODEL
        payload = {
            "model": modelo_a_usar,
            "prompt": prompt,
            "negative_prompt": negative_prompt,
            "width": 1024, "height": 1024, "steps": 30, "cfg_scale": 7.5,
            "return_binary": False, "safe_mode": False
        }
        data = await self._post_request("image/generate", payload)
        if isinstance(data, dict) and "images" in data:
            return base64.b64decode(data["images"][0])
        return None

    # --- UTILIDADES DE IMAGEN ---
    async def upscale_image(self, image_bytes, scale=2):
        if not image_bytes: return None
        img_b64 = base64.b64encode(image_bytes).decode('utf-8')
        payload = {"image": img_b64, "scale": scale}
        data = await self._post_request("image/upscale", payload)
        if isinstance(data, bytes): return data
        elif isinstance(data, dict) and "images" in data: return base64.b64decode(data["images"][0])
        elif isinstance(data, dict) and "image" in data: return base64.b64decode(data["image"])
        return None

    async def edit_image_prompt(self, image_bytes, prompt, model_id=None, strength=0.55):
        if not image_bytes: return None
        img_b64 = base64.b64encode(image_bytes).decode('utf-8')
        modelo_a_usar = model_id if model_id else VENICE_EDIT_MODEL

        # Intento 1: Generación Inyectada
        payload_hq = {
            "model": modelo_a_usar,
            "image": img_b64, "prompt": prompt,
            "strength": strength, "safe_mode": False
        }
        data = await self._post_request("image/generate", payload_hq)
        if isinstance(data, dict) and "images" in data: return base64.b64decode(data["images"][0])
        elif isinstance(data, dict) and "error" not in data: return None

        # Intento 2: Fallback Interno de Edición
        logger.warning("⚠️ Fallback a modo básico de edición...")
        payload_basic = {"image": img_b64, "prompt": prompt}
        data_retry = await self._post_request("image/edit", payload_basic)
        if isinstance(data_retry, bytes): return data_retry
        elif isinstance(data_retry, dict) and "images" in data_retry: return base64.b64decode(data_retry["images"][0])
        elif isinstance(data_retry, dict) and "image" in data_retry: return base64.b64decode(data_retry["image"])
        return None