import sys
import os
from sqlalchemy import text

# Boilerplate to find 'src' directory from scripts folder
sys.path.append(os.path.join(os.path.dirname(__file__), '../../src'))

from weather_engine.database import engine

def init_db():
    # Point this to your NEW sqlite sql file
    sql_path = os.path.join(os.path.dirname(__file__), '../../database/init.sql')
    
    print(f"Initializing SQLite DB from {sql_path}...")
    
    with open(sql_path, 'r') as f:
        # Split by ';' to handle multiple statements (DROP + CREATE)
        statements = f.read().split(';')
        
    with engine.connect() as conn:
        for statement in statements:
            if statement.strip():
                conn.execute(text(statement))
        conn.commit()
        print("Success: Table 'raw_station_data' created.")

if __name__ == "__main__":
    init_db()