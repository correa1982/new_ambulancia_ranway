import sqlite3
conn = sqlite3.connect('db.sqlite')
cursor = conn.cursor()
cursor.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='ths_sga_records'")
print(cursor.fetchone()[0])
