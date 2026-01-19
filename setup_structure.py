import os

# Definición de la estructura de carpetas y archivos base
structure = {
    "config": [
        "__init__.py",
        "settings.py",        # Configuración centralizada
        "logging_config.py"   # Logs estructurados
    ],
    "core": [
        "__init__.py",
        "bot.py",             # Lógica principal del bot
    ],
    "core/handlers": [        # Manejadores de eventos
        "__init__.py",
        "menu_handler.py",    # Lógica de menús
        "payment_handler.py", # Lógica de Telegram Stars
        "command_handler.py"  # Comandos básicos
    ],
    "services": [
        "__init__.py",
        "venice_service.py",  # Cliente API Venice
        "database_service.py" # Gestión de SQLite
    ],
    "utils": [
        "__init__.py",
        "security.py",        # Validaciones
        "helpers.py"          # Ayudas
    ],
    ".": [                    # Raíz
        "main.py",            # Punto de entrada
        ".env",               # Secretos
        ".gitignore",         # Seguridad git
        "requirements.txt",   # Dependencias
        "README.md"           # Documentación
    ]
}

env_content = """# Configuración de Secretos
BOT_TOKEN=tu_token_aqui
ADMIN_USER_ID=tu_id
VENICE_API_KEY=tu_api_key
VENICE_MODEL=venice-sd35
DATABASE_URL=sqlite:///./velzar.db
ENVIRONMENT=development
LOG_LEVEL=INFO
"""

gitignore_content = """
__pycache__/
*.pyc
.env
.DS_Store
velzar.db
"""

def create_structure():
    print("🚀 Iniciando creación de Velzar...")
    base_path = os.getcwd()

    for folder, files in structure.items():
        if folder != ".":
            folder_path = os.path.join(base_path, folder)
            os.makedirs(folder_path, exist_ok=True)
            print(f"📂 Carpeta: {folder}")
        else:
            folder_path = base_path

        for file in files:
            file_path = os.path.join(folder_path, file)
            if not os.path.exists(file_path):
                with open(file_path, "w", encoding="utf-8") as f:
                    if file == ".env": f.write(env_content)
                    elif file == ".gitignore": f.write(gitignore_content)
                    else: f.write(f"# Archivo: {file}\n")
                print(f"   📄 Creado: {file}")
            else:
                print(f"   ⚠️ Ya existía: {file}")

    print("\n✅ ¡Estructura completada, Amo Rubén!")

if __name__ == "__main__":
    create_structure()