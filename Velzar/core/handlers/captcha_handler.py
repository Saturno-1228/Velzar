import asyncio
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ChatPermissions
from telegram.ext import ContextTypes

# Diccionario temporal para usuarios pendientes: {user_id: chat_id}
PENDING_VERIFICATION = {}

async def new_member_captcha(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Función llamada cuando entra un nuevo miembro.
    Lo silencia y le envía un botón de verificación.
    """
    for member in update.message.new_chat_members:
        if member.is_bot: continue # Ignorar bots

        chat_id = update.effective_chat.id
        user_id = member.id
        name = member.first_name

        try:
            # 1. Silenciar al usuario (Mute preventivo)
            permissions = ChatPermissions(can_send_messages=False)
            await context.bot.restrict_chat_member(chat_id, user_id, permissions)

            # 2. Enviar mensaje con botón
            keyboard = [[InlineKeyboardButton("✅ SOY HUMANO / I AM HUMAN", callback_data=f"verify_{user_id}")]]
            msg = await update.message.reply_text(
                f"🛡️ **SISTEMA DE SEGURIDAD VELZAR**\n\n"
                f"👋 Hola {name}. Para evitar spam, por favor verifica que eres humano.\n"
                f"⏳ Tienes **120 segundos**.",
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode="Markdown"
            )

            # 3. Guardar estado (para tracking de kick por timeout - TODO en futuro)
            PENDING_VERIFICATION[user_id] = chat_id

            # 4. Tarea de fondo: Kick si no verifica en 2 min
            context.application.create_task(kick_if_unverified(context, chat_id, user_id, msg.message_id))

        except Exception as e:
            print(f"Error en Captcha: {e}")

async def verify_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    data = query.data
    user_id_target = int(data.split("_")[1])
    user_clicked = query.from_user.id

    # Solo el usuario afectado puede hacer click
    if user_clicked != user_id_target:
        await query.answer("❌ Este botón no es para ti / This button is not for you.", show_alert=True)
        return

    chat_id = update.effective_chat.id

    # Levantar mute
    try:
        # Permisos default para usuarios normales (enviar todo excepto añadir admins)
        permissions = ChatPermissions(
            can_send_messages=True,
            can_send_media_messages=True,
            can_send_other_messages=True,
            can_invite_users=True
        )
        await context.bot.restrict_chat_member(chat_id, user_clicked, permissions)

        # Actualizar mensaje
        await query.edit_message_text(f"✅ **Verificación Exitosa.** Bienvenido, {query.from_user.first_name}.", parse_mode="Markdown")

        if user_clicked in PENDING_VERIFICATION:
            del PENDING_VERIFICATION[user_clicked]

    except Exception as e:
        await query.edit_message_text(f"⚠️ Error al verificar: {e}")

async def kick_if_unverified(context, chat_id, user_id, message_id):
    await asyncio.sleep(120) # Esperar 2 minutos

    # Si sigue en la lista, es que no verificó
    if user_id in PENDING_VERIFICATION and PENDING_VERIFICATION[user_id] == chat_id:
        try:
            await context.bot.ban_chat_member(chat_id, user_id) # Ban
            await context.bot.unban_chat_member(chat_id, user_id) # Unban inmediato (soft kick)

            # Borrar el mensaje de captcha
            try:
                await context.bot.delete_message(chat_id, message_id)
            except:
                pass

            await context.bot.send_message(chat_id, f"🚫 **Usuario {user_id} expulsado por no verificar.**", parse_mode="Markdown")

            del PENDING_VERIFICATION[user_id]
        except Exception as e:
            print(f"Error en Auto-Kick: {e}")
