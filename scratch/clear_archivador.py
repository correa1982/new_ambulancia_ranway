import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from db import get_db

def clear_archivador():
    conn = get_db()
    cursor = conn.cursor()
    
    # Delete all records from the archivador table
    cursor.execute("DELETE FROM archivador")
    
    # Optional: Reset the autoincrement counter if desired
    try:
        cursor.execute("ALTER TABLE archivador AUTO_INCREMENT = 1")
    except Exception as e:
        print("Could not reset autoincrement (maybe not supported/needed):", e)
    
    conn.commit()
    conn.close()
    print("Archivador table has been cleared.")

if __name__ == "__main__":
    clear_archivador()
