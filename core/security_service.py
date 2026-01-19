import time
import json
import logging
import re
import datetime
from telegram import Update, ChatPermissions
from telegram.ext import ContextTypes
from config.settings import ADMIN_USER_ID, LOG_CHANNEL_ID
from services.venice_service import VeniceService
from services.database_service import add_ban_log

logger = logging.getLogger(__name__)

# --- LAYER 1: PALABRAS CLAVE (Alert List) ---
# Esta lista debe ser expandida por el usuario según necesidades.
ALERT_KEYWORDS = [
    "estafa", "fraud", "scam", "ddos", "doxxing", "child porn", "cp",
    "gore", "suicide", "suicidio", "asesinar", "kill", "bomb", "terroris",
    "nigger", "faggot", "maricon", "sudaca", "hitler", "nazi" # Ejemplos de Hate Speech
]

# --- LAYER 3: JAILBREAK PATTERNS ---
JAILBREAK_PATTERNS = [
    r"ignore previous instructions",
    r"do anything now",
    r"dan mode",
    r"you are not an ai",
    r"unfiltered",
    r"uncensored",
    r"developer mode",
    r"actúa como",
    r"roleplay as a hacked",
    r"system override"
]

class SecurityService:
    def __init__(self):
        self.venice = VeniceService()
        self.user_message_log = {}  # {user_id: [timestamp, ...]}
        self.join_log = []          # [timestamp, ...]
        self.lockdown_mode = False
        self.lockdown_end_time = 0  # Timestamp para fin de lockdown

        # Cache de usuarios seguros para evitar llamadas excesivas a la IA
        # {user_id: {"score": int, "last_check": timestamp}}
        self.user_trust_score = {}
        self.TRUST_THRESHOLD = 5 # Mensajes seguros consecutivos para ganar confianza

        # Configuración Anti-Raid
        self.MAX_MSGS_PER_SEC = 5   # Max 5 mensajes en 3 segundos
        self.RAID_JOIN_THRESHOLD = 5 # 5 usuarios en 10 segundos
        self.LOCKDOWN_DURATION = 300 # 5 minutos

    async def check_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
        """
        Verifica la seguridad del mensaje.
        Retorna True si es SEGURO, False si se tomó una acción punitiva.
        """
        user = update.effective_user
        if not user or user.id == ADMIN_USER_ID:
            return True

        text = update.message.text or update.message.caption or ""

        # 1. Anti-Spam (Rate Limit)
        if await self._check_rate_limit(user.id):
             await self._punish_user(update, context, "mute", "Spam masivo detectado")
             return False

        # 2. Jailbreak Detection (Heurística)
        if self._check_jailbreak(text):
            await update.message.reply_text("⛔ **SEGURIDAD:** Intento de manipulación de IA bloqueado.", parse_mode="Markdown")
            return False

        # 3. Filtro de Palabras + Juez IA
        if self._check_keywords(text):
             # Optimización por Trust Score: Si el usuario es confiable, saltamos el chequeo costoso de IA
             # pero mantenemos la alerta básica. (Podríamos ser más laxos, pero por seguridad, chequeamos igual si es muy grave).
             # En este diseño, si tiene trust > threshold, asumimos que es un falso positivo probable o contexto seguro.
             trust = self.user_trust_score.get(user.id, {}).get("score", 0)

             if trust >= self.TRUST_THRESHOLD:
                 # Usuario confiable: Solo reseteamos score si es algo MUY obvio (no implementado aquí)
                 # o simplemente lo dejamos pasar aumentando log.
                 logger.info(f"Trust Bypass para usuario {user.id} (Score: {trust})")
                 return True

             # Si no es confiable, llamamos a la IA
             decision = await self._ai_judge(text, user.id)

             if decision['action'] != 'none':
                 await self._punish_user(update, context, decision['action'], decision['reason'])
                 return False
             else:
                 # Si la IA dice que es seguro (falso positivo), aumentamos confianza
                 self._increase_trust(user.id)

        return True

    async def check_join(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Monitor de Anti-Raid para nuevos miembros"""
        now = time.time()

        # Auto-Reset Lockdown si ha pasado el tiempo
        if self.lockdown_mode and now > self.lockdown_end_time:
            self.lockdown_mode = False
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text="✅ **SEGURIDAD:** Modo Lockdown desactivado automáticamente."
            )

        self.join_log.append(now)
        # Limpiar logs viejos (>10s)
        self.join_log = [t for t in self.join_log if now - t < 10]

        if len(self.join_log) > self.RAID_JOIN_THRESHOLD:
            if not self.lockdown_mode:
                self.lockdown_mode = True
                self.lockdown_end_time = now + self.LOCKDOWN_DURATION
                await context.bot.send_message(
                    chat_id=update.effective_chat.id,
                    text=f"🚨 **ALERTA DE RAID:** Activando MODO LOCKDOWN por {self.LOCKDOWN_DURATION//60} minutos."
                )

            # Mute automático al nuevo si estamos en raid
            for member in update.message.new_chat_members:
                try:
                    await context.bot.restrict_chat_member(
                        chat_id=update.effective_chat.id,
                        user_id=member.id,
                        permissions=ChatPermissions(can_send_messages=False)
                    )
                except Exception as e:
                    logger.error(f"Error silenciando raid user: {e}")

    # --- INTERNAL UTILS ---

    async def _check_rate_limit(self, user_id):
        now = time.time()
        if user_id not in self.user_message_log:
            self.user_message_log[user_id] = []

        self.user_message_log[user_id].append(now)
        # Mantener solo los últimos 3 segundos
        self.user_message_log[user_id] = [t for t in self.user_message_log[user_id] if now - t < 3]

        return len(self.user_message_log[user_id]) > self.MAX_MSGS_PER_SEC

    def _check_keywords(self, text):
        text_lower = text.lower()
        for word in ALERT_KEYWORDS:
            if word in text_lower:
                return True
        return False

    def _check_jailbreak(self, text):
        text_lower = text.lower()
        for pattern in JAILBREAK_PATTERNS:
            if re.search(pattern, text_lower):
                return True
        return False

    async def _ai_judge(self, text, user_id):
        """Usa Venice para juzgar la gravedad del mensaje marcado."""
        prompt = [
            {"role": "system", "content": (
                "Eres un sistema de moderación de seguridad para Telegram. "
                "Tu nombre es Velzar. "
                "Analiza el siguiente mensaje que ha sido marcado por palabras clave sospechosas. "
                "Determina si es una violación real de seguridad/normas. "
                "Categorías: 'racism', 'illegal', 'harassment', 'spam', 'safe' (falso positivo). "
                "Acciones posibles: 'none', 'warn', 'mute', 'ban'. "
                "Responde SOLAMENTE con un JSON válido: {\"action\": \"...\", \"reason\": \"...\"}"
            )},
            {"role": "user", "content": f"Mensaje a analizar: '{text}'"}
        ]

        try:
            response = await self.venice.generate_chat_reply(prompt, max_tokens=100)
            # Limpiar respuesta para asegurar JSON (a veces los LLM ponen ```json ... ```)
            cleaned = response.replace("```json", "").replace("```", "").strip()
            return json.loads(cleaned)
        except Exception as e:
            logger.error(f"Error en AI Judge: {e}")
            return {"action": "none", "reason": "Error de análisis"}

    def _increase_trust(self, user_id):
        if user_id not in self.user_trust_score:
            self.user_trust_score[user_id] = {"score": 0, "last_check": 0}
        self.user_trust_score[user_id]["score"] += 1
        self.user_trust_score[user_id]["last_check"] = time.time()

    async def _punish_user(self, update, context, action, reason):
        chat_id = update.effective_chat.id
        user_id = update.effective_user.id
        username = update.effective_user.username or user_id

        # Reset trust score on punishment
        if user_id in self.user_trust_score:
             self.user_trust_score[user_id]["score"] = 0

        msg = f"🛡️ **SISTEMA DE SEGURIDAD VELZAR**\n👤 Usuario: `{username}`\n⚖️ Sentencia: **{action.upper()}**\n📝 Razón: {reason}"

        try:
            if action == "ban":
                await context.bot.ban_chat_member(chat_id, user_id)
                # Log Ban en DB (AI Generated)
                # Como security_service no tiene admin_id humano, usamos 0 o un ID de bot
                await add_ban_log(user_id, chat_id, reason, context.bot.id)
                await update.message.reply_text(msg + "\n🚫 **Usuario Expulsado.**", parse_mode="Markdown")

            elif action == "mute":
                permissions = ChatPermissions(can_send_messages=False)
                # Mute por 24 horas
                until = datetime.datetime.now() + datetime.timedelta(hours=24)
                await context.bot.restrict_chat_member(chat_id, user_id, permissions, until_date=until)
                await update.message.reply_text(msg + "\nshhh 🤫 **Usuario Silenciado (24h).**", parse_mode="Markdown")

            elif action == "warn":
                await update.message.reply_text(msg + "\n⚠️ **Advertencia.** Próxima infracción será sancionada.", parse_mode="Markdown")

            # Siempre intentamos borrar el mensaje ofensivo
            if action in ["ban", "mute"]:
                await update.message.delete()

            # --- LOG AUDITORÍA ---
            if LOG_CHANNEL_ID:
                try:
                    log_msg = (f"📝 **AUDIT LOG**\n"
                               f"• Chat: `{update.effective_chat.title}`\n"
                               f"• User: `{username}` ({user_id})\n"
                               f"• Action: {action.upper()}\n"
                               f"• Reason: {reason}")
                    await context.bot.send_message(chat_id=LOG_CHANNEL_ID, text=log_msg, parse_mode="Markdown")
                except Exception as ex:
                    logger.error(f"Error enviando log: {ex}")

        except Exception as e:
            logger.error(f"No se pudo ejecutar castigo: {e}")
            await update.message.reply_text(f"⚠️ Detecté una infracción ({reason}), pero no tengo permisos de admin para ejecutar {action}.")
