import sys
import os

# Add to path so db can be imported
sys.path.append(os.path.dirname(__file__))
from db import get_db

try:
    conn = get_db()
    print("Connected to DB.")
    cursor = conn.cursor()
    cursor.execute("DESCRIBE inventarios_historial")
    cols = cursor.fetchall()
    print("Columns in inventarios_historial:")
    for c in cols:
        print(c)
    
    print("\nExecuting SELECT * FROM inventarios_historial ORDER BY fecha_movimiento DESC LIMIT 1")
    res = conn.execute("SELECT * FROM inventarios_historial ORDER BY fecha_movimiento DESC").fetchall()
    print("Query success. Found", len(res), "rows.")
except Exception as e:
    print("Error:", e)
finally:
    if 'conn' in locals():
        conn.close()
