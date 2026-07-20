import sys
sys.path.append('.')
from db import get_db

try:
    with get_db() as conn:
        with conn.cursor() as cur:
            # Check if it already exists
            cur.execute("SHOW TABLES LIKE 'ths_soc_records'")
            if cur.fetchone():
                print("Table already exists")
            else:
                # Get schema of ths_sga_records
                cur.execute("SHOW CREATE TABLE ths_sga_records")
                res = cur.fetchone()
                schema = res['Create Table']
                
                # Replace the table name
                new_schema = schema.replace('`ths_sga_records`', '`ths_soc_records`')
                
                # Execute the creation
                cur.execute(new_schema)
                conn.commit()
                print("Successfully created ths_soc_records")
except Exception as e:
    print(f"Error: {e}")
