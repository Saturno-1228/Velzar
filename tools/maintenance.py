import os
import shutil
import sqlite3

def clean_temp_files():
    print("🧹 LIMPIEZA DE SISTEMA VELZAR")
    print("-----------------------------")

    # 1. Eliminar __pycache__
    print("🗑️ Eliminando caché de Python (__pycache__)...")
    count = 0
    for root, dirs, files in os.walk("."):
        if "__pycache__" in dirs:
            path = os.path.join(root, "__pycache__")
            try:
                shutil.rmtree(path)
                count += 1
            except Exception as e:
                print(f"   Error borrando {path}: {e}")
    print(f"   ✅ {count} carpetas eliminadas.")

    # 2. Optimizar Base de Datos
    if os.path.exists("velzar.db"):
        print("\n🗄️ Optimizando base de datos (VACUUM)...")
        try:
            conn = sqlite3.connect("velzar.db")
            conn.execute("VACUUM")
            conn.close()
            print("   ✅ Base de datos compactada.")
        except Exception as e:
            print(f"   ❌ Error optimizando DB: {e}")
    else:
        print("\n⚠️ No se encontró velzar.db")

    print("\n✨ Mantenimiento finalizado.")

if __name__ == "__main__":
    clean_temp_files()
    input("\nPresiona Enter para salir...")