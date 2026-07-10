"""
Script para insertar las aseguradoras SOAT en la base de datos.
"""
import os
import pymysql
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), '.env'))

ASEGURADORAS_SOAT = [
    "Allianz Colombia",
    "Aseguradora Solidaria de Colombia",
    "AXA Colpatria Seguros",
    "Compañía Mundial de Seguros",
    "HDI Seguros",
    "La Equidad Seguros",
    "La Previsora S.A. Compañía de Seguros",
    "Mapfre Seguros Generales de Colombia",
    "Seguros Bolívar",
    "Seguros del Estado",
    "Seguros Generales Suramericana",
]

def main():
    conn = pymysql.connect(
        host=os.getenv("MYSQL_HOST", "localhost"),
        user=os.getenv("MYSQL_USER", "root"),
        password=os.getenv("MYSQL_PASSWORD", ""),
        database=os.getenv("MYSQL_DB", "ambulancia_db"),
        port=int(os.getenv("MYSQL_PORT", 3306)),
        cursorclass=pymysql.cursors.DictCursor,
        charset="utf8mb4",
    )

    insertadas = 0
    omitidas = 0

    try:
        with conn.cursor() as cursor:
            for nombre in ASEGURADORAS_SOAT:
                cursor.execute("SELECT id FROM aseguradoras_soat WHERE nombre = %s", (nombre,))
                if cursor.fetchone():
                    print(f"  [OMITIDA]  {nombre}")
                    omitidas += 1
                else:
                    cursor.execute(
                        "INSERT INTO aseguradoras_soat (nombre, activo) VALUES (%s, 1)",
                        (nombre,)
                    )
                    print(f"  [OK]       {nombre}")
                    insertadas += 1
        conn.commit()
    finally:
        conn.close()

    print(f"\n{'='*55}")
    print(f"  Insertadas : {insertadas}")
    print(f"  Omitidas   : {omitidas}  (ya existían)")
    print(f"  Total      : {len(ASEGURADORAS_SOAT)}")
    print(f"{'='*55}")

if __name__ == "__main__":
    main()
