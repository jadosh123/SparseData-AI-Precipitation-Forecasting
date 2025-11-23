import pandas as pd
from sqlalchemy import create_engine, inspect, types
from sqlalchemy.dialects.postgresql import insert
import time
import os
import glob

# Database connection string
DB_CONN_STR = "postgresql+psycopg2://myuser:mypassword@db:5432/weather_db"

# Path to the data directory
DATA_DIR = "/app/cloud_data/"
TABLE_NAME = "raw_station_data"

# Station names and ID
STATION_MAP = {
    "Afula_Nir_HaEmek": 16, 
    "Tavor_Kadoorie": 13, 
    "Newe_Yaar": 186, 
    "Nazareth": 500,      # Matches Nazareth.xlsx
}

def insert_on_conflict_nothing(table, conn, keys, data_iter):
    """
    SQLAlchemy custom method for pandas to_sql that ignores duplicates.
    """
    # "data_iter" is a generator of rows. We need a list of dicts for SQLAlchemy.
    data = [dict(zip(keys, row)) for row in data_iter]
    
    # Build the standard INSERT statement
    stmt = insert(table.table).values(data)
    
    # Add the "ON CONFLICT DO NOTHING" clause
    # IMPORTANT: 'index_elements' must match your UNIQUE constraint columns!
    stmt = stmt.on_conflict_do_nothing(
        index_elements=['station_id', 'timestamp']
    )
    
    # Execute
    conn.execute(stmt)

def ingest_data():
    """
    Reads data from Excel files in a directory, transforms it, and ingests it into a PostgreSQL database.
    """
    # A more robust solution would be to use a proper wait-for-it script
    # or healthcheck in docker-compose.
    print("Waiting for database to be ready...")
    time.sleep(10)

    try:
        engine = create_engine(DB_CONN_STR)
        print("Database engine created.")

        files = glob.glob(os.path.join(DATA_DIR, '*.xlsx')) + glob.glob(os.path.join(DATA_DIR, '*.csv'))
        
        if not files:
            print(f"❌ No Excel or CSV files found in {DATA_DIR}")
            return

        print(f"📂 Found {len(files)} files to process.")

        for file_path in files:
            try:
                station_name = os.path.basename(file_path).split('.')[0]
                print(f"🚀 Processing: {station_name}")

                # CHANGE 2: Conditional Reading logic
                if file_path.endswith('.xlsx'):
                    # IMS Excel Format (Has 3 rows of metadata/headers)
                    df = pd.read_excel(
                        file_path, 
                        header=2, 
                        na_values=["NoData", "-", ""]
                    )
                else:
                    # CSV Logic
                    # NOTE: If your generated CSVs are clean (start with header), use header=0.
                    # If they look like IMS files (metadata at top), change to header=2.
                    try:
                        # Try UTF-8 first
                        df = pd.read_csv(file_path, header=0, na_values=["NoData", "-", ""])
                    except UnicodeDecodeError:
                        # Fallback for Hebrew/IMS encoding
                        df = pd.read_csv(file_path, header=0, na_values=["NoData", "-", ""], encoding='ISO-8859-8')

                # Smart Unit Dropping (Your existing logic - Keep this!)
                try:
                    first_row_values = df.iloc[0].astype(str).values.tolist()
                    unit_keywords = ['mm', 'deg', 'm/sec', 'degc', 'hpa']
                    if any(keyword in str(val).lower() for val in first_row_values for keyword in unit_keywords):
                        print(f"   Note: Detected units row. Dropping it.")
                        df = df.iloc[1:].reset_index(drop=True)
                except:
                    pass

                # Standard Cleaning
                df.columns = df.columns.str.strip().str.lower().str.replace(r'[\s\(\)]+', '_', regex=True).str.strip('_')

                # Timestamp Logic
                if 'date' in df.columns and 'time' in df.columns:
                    # Added 'dayfirst=True' because IMS uses DD/MM/YYYY
                    df['timestamp'] = pd.to_datetime(df['date'].astype(str) + ' ' + df['time'].astype(str), dayfirst=True, errors='coerce')
                    df = df.drop(columns=['date', 'time'])

                    # Fix for NULL timestamp entries
                    initial_count = len(df)
                    df = df.dropna(subset=['timestamp'])
                    dropped_count = initial_count - len(df)
                    if dropped_count > 0:
                        print(f"   ⚠️ Dropped {dropped_count} rows due to invalid timestamps.")

                elif 'timestamp' in df.columns:
                    # Logic for API CSVs (Already has timestamp column)
                    # Force conversion to ensure it's Datetime, not String
                    df['timestamp'] = pd.to_datetime(df['timestamp'], utc=True, errors='coerce')
                    
                    # Drop rows where conversion failed
                    df = df.dropna(subset=['timestamp'])
                    df = df.drop(columns=['time'], errors='ignore')

                # LOGIC FOR DEALING WITH STATION ID
                # Priority 1: Check if 'station_id' already exists in the file (API CSVs)
                if 'station_id' in df.columns:
                    print(f"   ℹ️ Using 'station_id' found inside the file.")
                    # Ensure it is numeric, just in case
                    df['station_id'] = pd.to_numeric(df['station_id'], errors='coerce')

                # We check if the filename STARTS with a known key to handle "Name_2020-2025"
                elif any(station_name.startswith(k) for k in STATION_MAP):
                    # Find the matching key
                    match = next(k for k in STATION_MAP if station_name.startswith(k))
                    print(f"   ℹ️ Mapped filename '{station_name}' to ID {STATION_MAP[match]}")
                    df['station_id'] = STATION_MAP[match]
                
                # Priority 3: Failure
                else:
                    print(f"❌ Error: No 'station_id' column in file AND filename '{station_name}' not in map. Skipping.")
                    continue

                # Force numeric types
                dtype_mapping = {
                    'timestamp': types.DateTime(),
                    'station_id': types.Integer()
                }
                
                numeric_cols = [col for col in df.columns if col not in ['timestamp', 'station_id']]
                for col in numeric_cols:
                    df[col] = pd.to_numeric(df[col], errors='coerce')
                    dtype_mapping[col] = types.Float

                # Reorder
                cols = ['timestamp', 'station_id'] + numeric_cols
                df = df[cols]

                # Upload with Conflict Handling
                df.to_sql(
                    TABLE_NAME,
                    engine,
                    if_exists='append',
                    index=False,
                    dtype=dtype_mapping,
                    method=insert_on_conflict_nothing,  # This is the key line
                    chunksize=2000
                )
                print(f"✅ Success: {station_name}")

            except Exception as e:
                print(f"⚠️ Error on {file_path}: {e}")

    except Exception as e:
        print(f"🔥 Critical Error: {e}")

if __name__ == "__main__":
    ingest_data()