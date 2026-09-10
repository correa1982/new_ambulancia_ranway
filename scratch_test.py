import os
import sys
sys.path.append(r"d:\GitHub\new_ambulancia_ranway")
from db import get_db
import traceback

try:
    conn = get_db()
    per_page = 50
    offset = 0
    movimientos = conn.execute("""
        SELECT ih.* 
        FROM inventarios_historial ih
        LEFT JOIN inventarios i ON ih.item_id = i.id
        WHERE i.tipo != 'Control Especial' OR i.tipo IS NULL
        ORDER BY ih.fecha_registro DESC LIMIT %s OFFSET %s
    """, (per_page, offset)).fetchall()
    print("Row:", movimientos[0])
    print("Type of fecha_registro:", type(movimientos[0]['fecha_registro']))
except Exception as e:
    print("ERROR:")
    traceback.print_exc()
