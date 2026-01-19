# 🛡️ Velzar Security Bot

**Velzar** es un sistema de seguridad avanzado y bot multifuncional para Telegram, diseñado para proteger grupos, moderar contenido con IA y ofrecer herramientas creativas.

## 🚀 Características Principales

### 🔒 Seguridad "Military Grade"
*   **Anti-Raid:** Detecta ataques masivos y activa el modo **Lockdown** automáticamente.
*   **Captcha:** Verificación obligatoria para nuevos miembros.
*   **Jailbreak Detection:** Protege a la IA de manipulaciones maliciosas.
*   **AI Judge:** Análisis inteligente de mensajes sospechosos usando **Venice.AI**.
*   **Trust Score:** Sistema de reputación para optimizar el uso de tokens y reducir falsos positivos.

### 🛠️ Herramientas de Administración
*   `/ban`, `/mute`, `/kick`, `/unban`: Comandos de moderación con registro en base de datos.
*   `/purge`: Limpieza masiva de mensajes.
*   `/auth` y `/unauth`: Gestión de permisos para operadores del bot.
*   **Modo Sigilo:** Los comandos de administración se eliminan automáticamente para mantener el chat limpio.

### 🤖 Resiliencia
*   **Self-Repair:** Cambio automático de modelo de IA si el principal falla.
*   **Auto-Restart:** Script de lanzamiento que reinicia el bot en caso de error.

---

## 📂 Estructura del Proyecto

El proyecto se ha reestructurado para facilitar su despliegue:

*   `core/`: Lógica principal del bot (handlers, seguridad).
*   `services/`: Conexiones externas (Venice AI, Base de Datos).
*   `config/`: Configuraciones y variables de entorno.
*   `tools/`: Scripts de mantenimiento y actualización.

---

## 🔧 Herramientas de Mantenimiento (`tools/`)

Hemos incluido scripts para facilitar la gestión del bot:

1.  **🔄 Auto-Updater (`tools/update_bot.py`)**
    *   Ejecuta este script para descargar la última versión del código desde GitHub y actualizar las librerías automáticamente.
    *   `python tools/update_bot.py`

2.  **🚀 Safe Launcher (`tools/start_bot.py`)**
    *   Usa este script para iniciar el bot. Si el bot falla o se cierra, lo reiniciará automáticamente.
    *   `python tools/start_bot.py`

3.  **🧹 Cleaner (`tools/maintenance.py`)**
    *   Herramienta para limpiar archivos temporales (`__pycache__`) y optimizar la base de datos.
    *   `python tools/maintenance.py`

---

## 📦 Instalación

1.  Clona el repositorio.
2.  Configura el archivo `.env` con tus claves (`BOT_TOKEN`, `VENICE_API_KEY`, etc.).
3.  Instala dependencias:
    ```bash
    pip install -r requirements.txt
    ```
4.  Inicia el bot con el lanzador seguro:
    ```bash
    python tools/start_bot.py
    ```

---

*Velzar Security Systems v2.5 | Developed for Rubén*