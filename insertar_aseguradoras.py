"""
Script para insertar las aseguradoras colombianas en la base de datos.
Usa INSERT IGNORE para no duplicar registros existentes.
"""
import os
import pymysql
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), '.env'))

ASEGURADORAS = [
    "Aliansalud EPS",
    "Anas Wayuu EPSI",
    "Asociación Indígena del Cauca",
    "Asmet Salud",
    "Cajacopi Atlántico",
    "Capital Salud EPS",
    "Capresoca",
    "Comfachocó",
    "Comfaoriente",
    "Comfenalco Valle",
    "Compensar EPS",
    "Coosalud",
    "Dusakawi EPSI",
    "Ecopetrol",
    "Empresas Públicas de Medellín",
    "Emssanar",
    "EPS Familiar de Colombia",
    "EPS Sanitas",
    "EPS Sura",
    "Famisanar",
    "Ferrocarriles Nacionales de Colombia",
    "Fondo Nacional de Prestaciones Sociales del Magisterio (FOMAG)",
    "Fuerzas Militares de Colombia",
    "Fundación Salud Mía",
    "Mallamas EPSI",
    "Mutual Ser",
    "Nueva EPS",
    "Pijaos Salud EPSI",
    "Policía Nacional Sanidad",
    "Programa de Salud Universidad de Antioquia",
    "Salud Total",
    "Savia Salud EPS",
    "Servicio Occidental de Salud (SOS)",
    "Unisalud Universidad Nacional de Colombia",
    "Universidad de Cartagena",
    "Universidad de Córdoba",
    "Universidad de Nariño",
    "Universidad del Atlántico",
    "Universidad del Cauca",
    "Universidad del Valle",
    "Universidad Industrial de Santander",
    "Universidad Pedagógica y Tecnológica de Colombia - UPTC",
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
            for nombre in ASEGURADORAS:
                # Verificar si ya existe
                cursor.execute("SELECT id FROM aseguradoras WHERE nombre = %s", (nombre,))
                if cursor.fetchone():
                    print(f"  [OMITIDA]  {nombre}")
                    omitidas += 1
                else:
                    cursor.execute(
                        "INSERT INTO aseguradoras (nombre, activo) VALUES (%s, 1)",
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
    print(f"  Total      : {len(ASEGURADORAS)}")
    print(f"{'='*55}")

if __name__ == "__main__":
    main()
