from db import get_db

def add_col():
    conn = get_db()
    try:
        conn.execute("ALTER TABLE nomina ADD COLUMN periodo VARCHAR(255)")
        conn.commit()
        print("Column added successfully!")
    except Exception as e:
        print("Error or already exists:", e)
    finally:
        conn.close()

if __name__ == '__main__':
    add_col()
