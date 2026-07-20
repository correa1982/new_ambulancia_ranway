from db import get_db

with get_db() as conn:
    with conn.cursor() as cursor:
        cursor.execute("SHOW CREATE TABLE ths_sga_records")
        res = cursor.fetchone()
        print(res[1])
