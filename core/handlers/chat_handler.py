import logging
from telegram import Update, MessageEntity
from telegram.ext import ContextTypes
from telegram.constants import ChatType

logger = logging.getLogger(__name__)

async def chat_reply_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Maneja la interacción de chat (Conversación).
    - Privado: Responde a todo.
    - Grupos: Responde solo a Menciones o Respuestas al Bot.
    """
    if not update.message or not update.message.text:
        return

    # Evitar loops o respuestas a otros bots (opcional, pero buena práctica)
    if update.message.from_user.is_bot:
        return

    chat_type = update.effective_chat.type
    text = update.message.text
    bot = context.bot
    bot_id = bot.id

    should_reply = False

    # Lógica de Decisión
    if chat_type == ChatType.PRIVATE:
        should_reply = True
    elif chat_type in [ChatType.GROUP, ChatType.SUPERGROUP]:
        # 1. Verificar si es reply al bot
        if update.message.reply_to_message and update.message.reply_to_message.from_user.id == bot_id:
            should_reply = True

        # 2. Verificar mención (@VelzarBot)
        if not should_reply and update.message.entities:
            for entity in update.message.entities:
                if entity.type == MessageEntity.MENTION:
                    # Verificar si la mención es a mí
                    mention_text = text[entity.offset:entity.offset + entity.length]
                    # Comparar con username del bot
                    if context.bot.username and mention_text.lower() == f"@{context.bot.username.lower()}":
                        should_reply = True
                        break
                elif entity.type == MessageEntity.TEXT_MENTION:
                    if entity.user.id == bot_id:
                        should_reply = True
                        break

    if not should_reply:
        return

    # --- Generar Respuesta ---

    # Notificar "Escribiendo..."
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")

    security_service = context.bot_data.get("security")
    if not security_service:
        logger.error("Security Service not initialized in bot_data")
        return

    # Historial de mensajes (Por ahora simple: solo el último mensaje)
    message_history = [{"role": "user", "content": text}]

    response_text = await security_service.venice.generate_chat_reply(message_history)

    if response_text:
        try:
            # Intentar Markdown primero (V1 es más permisivo que V2)
            await update.message.reply_text(response_text, parse_mode="Markdown")
        except Exception as e:
            # Fallback a texto plano si el Markdown está roto
            logger.warning(f"Error enviando Markdown: {e}. Enviando texto plano.")
            await update.message.reply_text(response_text)
