import subprocess
import sys
import time

def start_bot():
    print("🚀 INICIANDO VELZAR SYSTEM...")
    print("----------------------------")

    restart_count = 0

    while True:
        try:
            # Ejecutar main.py usando el mismo intérprete de Python
            process = subprocess.Popen([sys.executable, "main.py"])
            process.wait() # Esperar a que termine o falle

            # Si llega aquí, el bot se cerró
            exit_code = process.returncode

            if exit_code == 0:
                print("🛑 Bot detenido manualmente.")
                break
            else:
                restart_count += 1
                print(f"\n⚠️ CRASH DETECTADO (Código {exit_code}). Reiniciando en 5 segundos... (Intento {restart_count})")
                time.sleep(5)

        except KeyboardInterrupt:
            print("\n👋 Apagando sistema...")
            break
        except Exception as e:
            print(f"❌ Error crítico en el launcher: {e}")
            break

if __name__ == "__main__":
    start_bot()