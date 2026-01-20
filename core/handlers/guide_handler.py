import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

logger = logging.getLogger(__name__)

async def guide_callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Maneja la navegación del asistente de instalación interactivo.
    Patrón: ^guide_
    """
    query = update.callback_query
    await query.answer()

    data = query.data

    # Determinar la página actual basada en el callback_data
    # guide_main -> page 1
    # guide_page_X -> page X
    page = 1
    if data.startswith("guide_page_"):
        try:
            page = int(data.split("_")[-1])
        except ValueError:
            page = 1
    elif data == "guide_main":
        page = 1

    # Definir contenido por página
    text = ""
    buttons = []

    if page == 1:
        text = (
            "🛡️ **Bienvenido a Velzar.**\n\n"
            "Vamos a configurar tu seguridad en 3 pasos.\n"
            "Este asistente te guiará para blindar tu grupo correctamente."
        )
        buttons = [
            [
                InlineKeyboardButton("Siguiente ➡️", callback_data="guide_page_2")
            ],
            [
                InlineKeyboardButton("❌ Finalizar", callback_data="back_home")
            ]
        ]

    elif page == 2:
        text = (
            "1️⃣ **Permisos de Administrador**\n\n"
            "Necesito permisos de Administrador para protegerte.\n"
            "Asegúrate de otorgarme los siguientes derechos:\n"
            "• ❌ Banear usuarios\n"
            "• 🗑️ Borrar mensajes\n"
            "• 📌 Anclar mensajes\n\n"
            "Sin esto, no podré actuar contra amenazas."
        )
        buttons = [
            [
                InlineKeyboardButton("⬅️ Anterior", callback_data="guide_page_1"),
                InlineKeyboardButton("Siguiente ➡️", callback_data="guide_page_3")
            ],
            [
                InlineKeyboardButton("❌ Finalizar", callback_data="back_home")
            ]
        ]

    elif page == 3:
        text = (
            "2️⃣ **Canal de Logs (Reportes)**\n\n"
            "Crea un canal privado y usa el comando `/setlog` en tu grupo para vincularlo.\n\n"
            "Ejemplo:\n"
            "`/setlog -100123456789`\n\n"
            "Allí enviaré evidencias de bans y auditorías."
        )
        buttons = [
            [
                InlineKeyboardButton("⬅️ Anterior", callback_data="guide_page_2"),
                InlineKeyboardButton("Siguiente ➡️", callback_data="guide_page_4")
            ],
            [
                InlineKeyboardButton("❌ Finalizar", callback_data="back_home")
            ]
        ]

    elif page == 4:
        text = (
            "3️⃣ **Prueba Final**\n\n"
            "¡Listo! La configuración básica está completa.\n\n"
            "Para probarme, responde a cualquier mensaje en tu grupo con:\n"
            "`/check`\n\n"
            "Analizaré el mensaje con mi IA y te daré un veredicto."
        )
        buttons = [
            [
                InlineKeyboardButton("⬅️ Anterior", callback_data="guide_page_3")
            ],
            [
                InlineKeyboardButton("❌ Finalizar", callback_data="back_home")
            ]
        ]

    # Editar mensaje
    await query.edit_message_text(
        text=text,
        reply_markup=InlineKeyboardMarkup(buttons),
        parse_mode="Markdown"
    )
