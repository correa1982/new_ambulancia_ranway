import sqlite3

conn = sqlite3.connect(r'c:\Users\Danni Mejia\Documents\GitHub\new_ambulancia_ranway\db.sqlite')
conn.row_factory = sqlite3.Row

cursor = conn.execute("SELECT * FROM nomina ORDER BY id DESC LIMIT 2")
nominas = cursor.fetchall()
print("Nominas:")
for n in nominas:
    print(dict(n))

cursor = conn.execute("SELECT id, nomina_id, identificacion, nombres, codigo, valor_total FROM nomina_empleados")
empleados = cursor.fetchall()
print("\nEmpleados:")
for e in empleados:
    print(dict(e))

conn.close()
