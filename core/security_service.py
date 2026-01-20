import logging
import re
import time
import asyncio
from telegram import Update, ChatPermissions
from telegram.ext import ContextTypes
from services.venice_service import VeniceService
from services.database_service import (
    get_or_create_user, update_trust_score, add_ban_log,
    get_authorized_admins, get_chat_settings
)
from config.settings import ADMIN_USER_ID

logger = logging.getLogger(__name__)

class SecurityService:
    def __init__(self):
        self.venice = VeniceService()
        self.flood_control = {} # Estructura: {user_id: [timestamp1, timestamp2, ...]}

        # --- COMPILADOR DE REGEX (Capa 2) ---
        # Patrones de Estafa e Insultos (Pack Inicial)
        self.regex_patterns = [
            # Links de Estafa Comunes
            re.compile(r'(https?://)?(t\.me/\+|bit\.ly|tinyurl\.com|is\.gd)', re.IGNORECASE),
            # Palabras Clave de Crypto Scam (Español/Inglés)
            re.compile(r'(inversión|ganancia|rentabilidad|profit|bitcoin|crypto|usdt).*(garantizada|segura|gratis|giveaway)', re.IGNORECASE),
            re.compile(r'(invest|make money|passive income|doubling)', re.IGNORECASE),
            # Insultos Graves (Español Latino/MX)
            re.compile(r'\b(est[uú]pido|idiota|pendejo|imb[eé]cil|mierda|puto|verga|chinga|zorra|malparido)\b', re.IGNORECASE)
        ]

    async def check_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
        """
        Punto de entrada principal de seguridad.
        Retorna True si el mensaje es SEGURO, False si se tomó acción punitiva.
        """
        if not update.effective_user or not update.effective_chat:
            return True

        user = update.effective_user
        chat = update.effective_chat
        text = update.effective_message.text or update.effective_message.caption or ""

        # Solo aplicar en Grupos/Supergrupos (En privado el usuario hace lo que quiere con el bot)
        if chat.type == "private":
            return True

        # --- CAPA 0: INMUNIDAD (Dueño y Admins) ---
        if await self._is_immune(user.id, chat.id, context):
            return True

        # --- CAPA 1: ANTI-FLOOD Y MEDIOS ---
        if await self._check_flood(user.id):
            await self._punish_user(update, context, reason="Flood Detectado", action="mute")
            return False

        # (Futuro: Aquí iría filtro de medios/reenviados si se habilita)

        # --- CAPA 2: REGEX (Patrones Locales) ---
        for pattern in self.regex_patterns:
            if pattern.search(text):
                await self._punish_user(update, context, reason="Patrón Prohibido (Regex)", action="ban")
                return False

        # --- CAPA 3: TRUST SCORE (Ahorro de Costos) ---
        db_user = await get_or_create_user(user.id, user.username)
        trust_score = db_user["trust_score"]

        if trust_score >= 10:
            # Usuario confiable, pase directo (+1 punto por buen comportamiento)
            await update_trust_score(user.id, increment=True)
            return True

        # --- CAPA 4: IA VENICE (Clasificación Quirúrgica) ---
        # Solo analizamos si hay texto suficiente (más de 3 caracteres)
        if len(text) > 3:
            analysis = await self.venice.classify_message(text)
            risk = analysis.get("risk", "LOW")
            reason = analysis.get("reason", "Análisis IA")

            if risk == "HIGH":
                await self._punish_user(update, context, reason=f"IA High Risk: {reason}", action="ban")
                await update_trust_score(user.id, reset=True)
                return False
            elif risk == "MED":
                await self._punish_user(update, context, reason=f"IA Medium Risk: {reason}", action="mute")
                await update_trust_score(user.id, reset=True)
                return False
            else:
                # Riesgo BAJO -> Permitir y subir reputación
                await update_trust_score(user.id, increment=True)
                return True

        return True

    async def check_join(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Verifica nuevos miembros."""
        # Por ahora solo pasamos, la lógica de bienvenida se maneja en el handler principal si pasa
        return True

    # --- MÉTODOS PRIVADOS ---

    async def _is_immune(self, user_id: int, chat_id: int, context: ContextTypes.DEFAULT_TYPE) -> bool:
        """Verifica si el usuario es inmune (Dueño, Admin del Bot o Admin del Chat)."""
        # 1. Dueño del Bot
        if user_id == int(ADMIN_USER_ID):
            return True

        # 2. Admins Autorizados del Bot (DB)
        authorized_admins = await get_authorized_admins()
        if user_id in authorized_admins:
            return True

        # 3. Admins del Chat actual
        try:
            chat_member = await context.bot.get_chat_member(chat_id, user_id)
            if chat_member.status in ["creator", "administrator"]:
                return True
        except Exception as e:
            logger.warning(f"Error verificando admin del chat: {e}")

        return False

    async def _check_flood(self, user_id: int) -> bool:
        """Retorna True si el usuario está haciendo flood (>5 mensajes en 3s)."""
        now = time.time()
        timestamps = self.flood_control.get(user_id, [])

        # Limpiar timestamps viejos (> 3 segundos)
        timestamps = [t for t in timestamps if now - t < 3.0]

        # Agregar actual
        timestamps.append(now)
        self.flood_control[user_id] = timestamps

        if len(timestamps) > 5:
            return True
        return False

    async def _punish_user(self, update: Update, context: ContextTypes.DEFAULT_TYPE, reason: str, action: str):
        """Ejecuta el castigo y loguea la acción."""
        chat = update.effective_chat
        user = update.effective_user

        try:
            # Eliminar mensaje ofensivo
            await update.effective_message.delete()
        except Exception:
            pass # Puede que ya esté borrado o falten permisos

        try:
            if action == "ban":
                await chat.ban_member(user.id)
                await context.bot.send_message(chat.id, f"🛡️ **BANNED:** {user.first_name}\n📝 **Razón:** {reason}", parse_mode="Markdown")
            elif action == "mute":
                permissions = ChatPermissions(can_send_messages=False)
                # Mute por 1 hora por defecto
                until_date = time.time() + 3600
                await chat.restrict_member(user.id, permissions, until_date=until_date)
                await context.bot.send_message(chat.id, f"🛡️ **MUTED:** {user.first_name}\n📝 **Razón:** {reason}", parse_mode="Markdown")

            # Registrar en DB
            # (Asumimos admin_id 0 para el bot)
            await add_ban_log(user.id, chat.id, reason, 0)

            # Loguear a Canal de Auditoría
            await self._log_action(context, chat.id, user, action, reason)

        except Exception as e:
            logger.error(f"Fallo al castigar usuario {user.id}: {e}")
            await context.bot.send_message(chat.id, "⚠️ Error de permisos. Hazme Admin para protegerte.")

    async def _log_action(self, context: ContextTypes.DEFAULT_TYPE, chat_id: int, user, action: str, reason: str):
        """Envía el log al canal configurado."""
        settings = await get_chat_settings(chat_id)
        if settings and settings["log_channel_id"]:
            log_channel = settings["log_channel_id"]
            log_text = (
                f"#{action.upper()} | User: {user.full_name} | ID: `{user.id}`\n"
                f"Reason: {reason} | By: Velzar"
            )
            try:
                await context.bot.send_message(log_channel, log_text, parse_mode="Markdown")
            except Exception as e:
                logger.warning(f"No se pudo enviar log al canal {log_channel}: {e}")
