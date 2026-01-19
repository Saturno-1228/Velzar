import os
import subprocess
import sys

def run_command(command):
    try:
        result = subprocess.run(command, shell=True, check=True, text=True, capture_output=True)
        print(result.stdout)
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ Error ejecutando: {command}")
        print(e.stderr)
        return False

def update_repo():
    print("🔄 VELZAR AUTO-UPDATER")
    print("----------------------")
    print("📡 Conectando con GitHub...")

    # 1. Pull changes
    if run_command("git pull"):
        print("✅ Código actualizado correctamente.")
    else:
        print("⚠️ Hubo un problema al actualizar. Verifica tu conexión o conflictos de git.")
        return

    # 2. Check dependencies
    print("\n📦 Verificando dependencias...")
    if os.path.exists("requirements.txt"):
        run_command(f"{sys.executable} -m pip install -r requirements.txt")
        print("✅ Dependencias al día.")
    else:
        print("⚠️ No se encontró requirements.txt")

    print("\n🎉 Actualización completada. Puedes reiniciar el bot.")

if __name__ == "__main__":
    update_repo()
    input("\nPresiona Enter para salir...")