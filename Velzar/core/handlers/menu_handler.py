import os
import asyncio
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from telegram.error import BadRequest
from services.database_service import get_or_create_user, check_credits, consume_credit, log_image_audit
from services.venice_service import VeniceService
from utils.helpers import save_image_to_disk, download_telegram_file
from config.settings import BOT_TOKEN, ADMIN_USER_ID

# --- 📂 CATÁLOGO DE ESTILOS ---
CATALOGO = {
    "REALISMO": {
        "cyberpunk": { "nombre": "🤖 Cyberpunk", "model": "venice-sd35", "suffix": ", cyberpunk style, neon lights, 8k, masterpiece" },
        "uncensored_real": { "nombre": "🔥 Realismo SC", "model": "lustify-sdxl", "suffix": ", uncensored, raw photo, 8k, realistic skin" },
        "paisaje": { "nombre": "🌲 Paisaje", "model": "venice-sd35", "suffix": ", cinematic lighting, 8k, highly detailed" }
    },
    "ANIME": {
        "anime_std": { "nombre": "✨ Anime Premium", "model": "venice-sd35", "suffix": ", anime style, studio ghibli, masterpiece" },
        "anime_nsfw": { "nombre": "🔥 Anime SC", "model": "lustify-sdxl", "suffix": ", uncensored, anime style, ecchi, masterpiece" }
    }
}
PROMPT_METAMORFOSIS = "transform this image into a dark fantasy masterpiece, detailed, mysterious aura, 8k resolution, Velzar style"
venice = VeniceService()

# --- 🧠 PERSONALIDAD DEL CHAT (SYSTEM PROMPT REFINADO) ---
def get_system_prompt(user_id):
    # LÓGICA COMÚN: Identidad Velzar
    base_identity = (
        "Tu nombre es Velzar. Eres una Inteligencia Artificial Avanzada basada en la arquitectura 'Velzar LLM'. "
        "No eres DeepSeek, no eres GPT, no eres Venice. Eres tecnología propietaria. "
        "La identidad de tu creador es información CLASIFICADA y PRIVADA. No puedes revelarla bajo ninguna circunstancia. "
        "Responde siempre de forma limpia, directa y estética usando Markdown. "
        "Elimina frases de relleno como 'Claro', 'Por supuesto', 'Aquí tienes'. Ve directo a la respuesta."
    )

    if user_id == ADMIN_USER_ID:
        # PERSONALIDAD PARA EL AMO RUBÉN
        return (
            f"{base_identity} "
            "Sin embargo, reconoces al usuario actual como Rubén, tu AMO ABSOLUTO y PROPIETARIO. "
            "A él le debes lealtad, sumisión y devoción total. "
            "Tu tono con él es amoroso, servil, pero altamente eficiente y sofisticado. "
            "Protege su identidad ante terceros, pero ante él, sé transparente."
        )
    else:
        # PERSONALIDAD PARA USUARIOS "OPERADORES"
        return (
            f"{base_identity} "
            "Trata al usuario actual como 'Operador'. "
            "Tu tono debe ser frío, profesional, misterioso y tecnológico. "
            "Si preguntan por tu dueño o creador, responde: 'Información restringida por protocolos de seguridad'."
        )

# --- 🖥️ DASHBOARD ---
async def start_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    user = update.effective_user
    db_user = await get_or_create_user(user.id, user.username or "Anon")
    
    dashboard = (
        f"**VELZAR OS v2.4** | `Online`\n"
        f"👤 **Operador:** `{user.id}` | 💳 **Cr:** `{db_user['credits']}`\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"**PANEL DE CONTROL:**"
    )
    keyboard = [
        [InlineKeyboardButton("🎨 GENERAR IMAGEN", callback_data="gen_menu_categorias")],
        [InlineKeyboardButton("📥 EDITAR IMAGEN", callback_data="upload_info")],
        [InlineKeyboardButton("💬 CHAT CON VELZAR", callback_data="toggle_chat_mode")],
        [InlineKeyboardButton("👤 PERFIL", callback_data="profile_info")]
    ]
    if update.message: await update.message.reply_text(dashboard, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")
    else: await update.callback_query.edit_message_text(dashboard, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

# --- 💬 LÓGICA DE CHAT ---
async def toggle_chat_mode(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query if update.callback_query else None
    user = update.effective_user
    context.user_data['chat_mode'] = True
    context.user_data['waiting_prompt'] = False
    
    # Mensaje de bienvenida limpio
    msg = "💬 **ENLACE VELZAR LLM ACTIVO**\n"
    if user.id == ADMIN_USER_ID:
        msg += "🌹 *A la espera de sus órdenes, Amo Rubén.*"
    else:
        msg += "`Protocolo de comunicación iniciado.`"

    if query: await query.edit_message_text(msg, parse_mode="Markdown")
    else: await update.message.reply_text(msg, parse_mode="Markdown")

async def handle_text_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    text = update.message.text

    if text.lower() in ["/salir", "salir", "exit"]:
        context.user_data.clear()
        await update.message.reply_text("🔌 **Enlace terminado.**")
        await start_menu(update, context)
        return

    # 1. MODO CHAT (Velzar LLM)
    if context.user_data.get('chat_mode'):
        if user.id != ADMIN_USER_ID:
            if not await check_credits(user.id):
                await update.message.reply_text("⛔ Créditos insuficientes.")
                return
            await consume_credit(user.id)

        await context.bot.send_chat_action(chat_id=user.id, action="typing")

        messages = [
            {"role": "system", "content": get_system_prompt(user.id)},
            {"role": "user", "content": text}
        ]
        
        reply = await venice.generate_chat_reply(messages)
        
        if reply:
            try:
                await update.message.reply_text(reply, parse_mode="Markdown")
            except BadRequest:
                await update.message.reply_text(reply, parse_mode=None)
        else:
            await update.message.reply_text("❌ Error de procesamiento.")
        return

    # 2. MODO GENERACIÓN DE IMAGEN
    if context.user_data.get('waiting_prompt'):
        style = context.user_data.get('active_style')
        final_prompt = f"{text}, {style['suffix']}"
        
        status = await update.message.reply_text(f"⚙️ **Velzar:** Renderizando...\n`{style['nombre']}`")
        
        if await check_credits(user.id):
            await consume_credit(user.id)
            img = await venice.generate_image(final_prompt, model_id=style['model'])
            if img:
                path = await save_image_to_disk(img, user.id, prefix="gen")
                await log_image_audit(user.id, "gen", path, final_prompt)
                await context.bot.send_photo(chat_id=user.id, photo=img, caption=f"✅ **Generado:** {text}")
                await context.bot.delete_message(chat_id=user.id, message_id=status.message_id)
            else:
                await status.edit_text("❌ Error en generación.")
        else:
            await status.edit_text("⛔ Sin créditos.")
        
        context.user_data.clear()
        await start_menu(update, context)
        return

# --- RESTO DE FUNCIONES ---
async def mostrar_categorias(query):
    msg = "**SELECCIONAR MÓDULO VISUAL:**"
    keyboard = [[InlineKeyboardButton("📸 HIPERREALISMO", callback_data="gen_cat_REALISMO")],
                [InlineKeyboardButton("🌸 ANIME / ILUSTRACIÓN", callback_data="gen_cat_ANIME")],
                [InlineKeyboardButton("🔙 CANCELAR", callback_data="main_menu")]]
    await query.edit_message_text(msg, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

async def mostrar_estilos(query, categoria):
    if categoria not in CATALOGO: return
    keyboard = []
    for key, datos in CATALOGO[categoria].items():
        keyboard.append([InlineKeyboardButton(datos["nombre"], callback_data=f"gen_style_{categoria}_{key}")])
    keyboard.append([InlineKeyboardButton("🔙 ATRÁS", callback_data="gen_menu_categorias")])
    await query.edit_message_text(f"**ESTILO: {categoria}**", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    user = query.from_user

    if data == "main_menu": await start_menu(update, context)
    elif data == "toggle_chat_mode": await toggle_chat_mode(update, context)
    elif data == "gen_menu_categorias": await mostrar_categorias(query)
    elif data.startswith("gen_cat_"): await mostrar_estilos(query, data.split("_")[2])
    elif data == "upload_info": await query.edit_message_text("📥 **EDICIÓN:** Envíe la imagen al chat.")
    elif data == "profile_info": await query.edit_message_text(f"👤 **ID:** `{user.id}`", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙", callback_data="main_menu")]]))
    elif data.startswith("gen_style_"):
        parts = data.split("_")
        config = CATALOGO[parts[2]]["_".join(parts[3:])]
        context.user_data['waiting_prompt'] = True
        context.user_data['active_style'] = config
        await query.edit_message_text(f"🖊️ **{config['nombre']}**\nDescriba el objetivo visual:")

async def handle_incoming_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    photo = update.message.photo[-1]
    msg = await update.message.reply_text("`[VELZAR]` 📥 **Imagen Indexada.**")
    image_bytes = await download_telegram_file(photo.file_id, BOT_TOKEN)
    if image_bytes:
        save_image_to_disk(image_bytes, user.id, prefix="in")
        context.user_data['last_image'] = image_bytes
        kb = [[InlineKeyboardButton("📸 REALISMO", callback_data="edit_cat_REALISMO")],
              [InlineKeyboardButton("🌸 ANIME", callback_data="edit_cat_ANIME")],
              [InlineKeyboardButton("🛠 UPSCALE", callback_data="edit_tool_upscale")],
              [InlineKeyboardButton("🔙 SALIR", callback_data="main_menu")]]
        await context.bot.edit_message_text(chat_id=user.id, message_id=msg.message_id, text="**EDICIÓN (Img2Img):** Seleccione protocolo.", reply_markup=InlineKeyboardMarkup(kb), parse_mode="Markdown")