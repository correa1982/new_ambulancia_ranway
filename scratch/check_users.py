import sqlite3

def fix_db():
    conn = sqlite3.connect(r'c:\Users\Danni Mejia\Documents\GitHub\new_ambulancia_ranway\db.sqlite')
    cursor = conn.cursor()
    # Check what user 2 is
    cursor.execute("SELECT * FROM usuarios WHERE id = 2")
    user2 = cursor.fetchone()
    print("User 2:", user2)

    # Check user 1
    cursor.execute("SELECT * FROM usuarios WHERE id = 1")
    user1 = cursor.fetchone()
    print("User 1:", user1)

    conn.close()

if __name__ == "__main__":
    fix_db()
