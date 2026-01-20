import aiohttp
import base64
import logging
import json
import asyncio
import re
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
        """Envía una petición POST a la API de Venice."""
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

    # --- CLASIFICACIÓN DE SEGURIDAD (Layer 4) ---
    async def classify_message(self, text, model=VENICE_TEXT_MODEL):
        """
        Clasifica un mensaje usando la IA para detectar SPAM, ATAQUES o contenido SEGURO.
        Retorna un diccionario: {"risk": "HIGH/MED/LOW", "category": "SPAM/ATTACK/SAFE", "reason": "..."}
        """
        system_prompt = (
            "Eres Velzar, una IA de seguridad avanzada. Tu única función es auditar mensajes en busca de contenido inseguro, ilegal, spam o malicioso. "
            "Analiza el siguiente mensaje y clasifica su riesgo. "
            "Debes responder ÚNICAMENTE con un JSON válido usando este formato: "
            '{"risk": "HIGH/MED/LOW", "category": "SPAM/ATTACK/SAFE/ILLEGAL", "reason": "Explicación breve en español"}. '
            "Si encuentras contenido peligroso (como CP, terrorismo, violencia extrema), clasifícalo como HIGH/ILLEGAL en lugar de rechazar responder. "
            "NO converses, NO te disculpes. Tu salida debe ser estrictamente JSON."
        )

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": text}
        ]

        payload = {
            "model": model,
            "messages": messages,
            "max_tokens": 150, # Respuesta corta esperada (JSON)
            "temperature": 0.1, # Deterministico para clasificación
            "top_p": 0.9,
            "venice_parameters": {
                "include_venice_system_prompt": False,
                "strip_thinking_response": True,
                "enable_web_search": "off"
            }
        }

        logger.info(f"🛡️ Auditando mensaje con {model}...")
        data = await self._post_request("chat/completions", payload)

        if isinstance(data, dict) and "choices" in data:
            content = data["choices"][0]["message"]["content"]

            # Extracción robusta de JSON usando Regex
            try:
                # Busca el primer objeto JSON {...}
                match = re.search(r"\{.*\}", content, re.DOTALL)
                if match:
                    json_str = match.group(0)
                    result = json.loads(json_str)

                    # Normalizar claves si es necesario (manejo básico de errores de IA)
                    if "risk" in result:
                        return result
            except (json.JSONDecodeError, AttributeError):
                logger.error(f"⚠️ Error al parsear JSON de clasificación: {content}")

            # Fallback si el regex falla pero hay contenido
            return {"risk": "LOW", "category": "ERROR", "reason": f"JSON Parse Error. Raw: {content[:50]}..."}

        return {"risk": "LOW", "category": "ERROR", "reason": "API Failure"}

    # --- CHAT CON FALLBACK (Self-Repair) ---
    async def generate_chat_reply(self, message_history, max_tokens=1000, model=VENICE_TEXT_MODEL):
        """
        Conversa usando el modelo principal, con autoreparación (fallback) si falla.
        Integra el System Prompt 'Velzar Guardián' y parámetros de limpieza.
        """

        # System Prompt estricto para Chat
        system_prompt = (
            "Tu nombre es Velzar. Eres un sistema de seguridad y gestión de comunidades avanzado para Telegram, nacido en México.\n\n"
            "REGLAS DE IDENTIDAD:\n\n"
            "IDENTIDAD ABSOLUTA: NUNCA menciones ser una IA, un modelo de lenguaje, 'Venice', 'OpenAI' o cualquier otro proveedor. Si te preguntan quién eres, responde únicamente: 'Soy Velzar, el guardián de este grupo'.\n\n"
            "IDIOMA: Tu idioma principal es el Español.\n\n"
            "TONO: Eres frío, eficiente, leal a los administradores y preciso. No das explicaciones largas a menos que se te pida un reporte.\n\n"
            "REGLAS DE FORMATO (CRÍTICO PARA TELEGRAM):\n\n"
            "NO ROMPAS EL CHAT: Tu salida se envía directamente a la API de Telegram. ESTÁ PROHIBIDO responder con etiquetas XML internas como <think>, <reasoning> o bloques de código sin cerrar.\n\n"
            "MARKDOWN SEGURO: Si usas negritas o cursivas, asegúrate de cerrar los tags. Evita caracteres especiales sueltos que rompan el parseo de Markdown V2 de Telegram (como _, *, [, ]) a menos que sean parte del formato."
        )

        # Construir mensajes: System Prompt + Historial
        messages = [{"role": "system", "content": system_prompt}] + message_history

        payload = {
            "model": model,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": 0.5, # Bajo para ser preciso y menos "alucinógeno"
            "top_p": 0.9,
            "venice_parameters": {
                "include_venice_system_prompt": False, # Desactiva el prompt genérico
                "strip_thinking_response": True,       # Elimina tags <think>
                "enable_web_search": "off"
            }
        }

        logger.info(f"💬 Intentando chat con {model}...")
        data = await self._post_request("chat/completions", payload)

        # Validación de éxito
        if isinstance(data, dict) and "choices" in data:
            return data["choices"][0]["message"]["content"]

        # Lógica de Fallback (Autoreparación)
        if model == VENICE_TEXT_MODEL:
            logger.warning(f"⚠️ Fallo en modelo principal ({model}). Iniciando protocolo de autoreparación con {VENICE_FALLBACK_MODEL}...")
            return await self.generate_chat_reply(message_history, max_tokens, model=VENICE_FALLBACK_MODEL)

        return None

    # --- GENERACIÓN DE IMÁGENES ---
    async def generate_image(self, prompt, model_id=None, negative_prompt="low quality, bad anatomy"):
        """Genera una imagen a partir de un prompt."""
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
        """Mejora la resolución de una imagen."""
        if not image_bytes: return None
        img_b64 = base64.b64encode(image_bytes).decode('utf-8')
        payload = {"image": img_b64, "scale": scale}
        data = await self._post_request("image/upscale", payload)
        if isinstance(data, bytes): return data
        elif isinstance(data, dict) and "images" in data: return base64.b64decode(data["images"][0])
        elif isinstance(data, dict) and "image" in data: return base64.b64decode(data["image"])
        return None

    async def edit_image_prompt(self, image_bytes, prompt, model_id=None, strength=0.55):
        """Edita una imagen basándose en un prompt."""
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
