import pandas as pd
from sqlalchemy import create_engine, inspect, types
from sqlalchemy.dialects.postgresql import insert
import time
import os
import glob
from pathlib import Path
from dotenv import load_dotenv

base_dir = Path(__file__).resolve().parent.parent
env_file = base_dir / '.env'
load_dotenv(env_file)
db_user = os.getenv("POSTGRES_USER")
db_pass = os.getenv("POSTGRES_PASSWORD")
db_host = os.getenv("DB_HOST")
db_name = os.getenv("POSTGRES_DB")

DB_CONN_STR = f"postgresql+psycopg2://{db_user}:{db_pass}@{db_host}:5432/{db_name}"
DATA_DIR = "/app/cloud_data/"
TABLE_NAME = "raw_station_data"

STATION_MAP = {
    "Afula_Nir_HaEmek": 16, 
    "Tavor_Kadoorie": 13,
    "Newe_Yaar": 186,
    "Nazareth_City": 500,
    "Haifa_Technion": 43
}

def insert_on_conflict_nothing(table, conn, keys, data_iter):
    """
    Custom insert method to handle duplicates via ON CONFLICT DO NOTHING.
    """
    data = [dict(zip(keys, row)) for row in data_iter]
    stmt = insert(table.table).values(data)
    stmt = stmt.on_conflict_do_nothing(index_elements=['station_id', 'timestamp'])
    conn.execute(stmt)

def ingest_data():
    print("Waiting for database...")
    time.sleep(10)

    try:
        engine = create_engine(DB_CONN_STR)
        print("Database engine connected.")

        files = glob.glob(os.path.join(DATA_DIR, '*.xlsx')) + glob.glob(os.path.join(DATA_DIR, '*.csv'))
        # files = glob.glob(os.path.join(DATA_DIR, '*Nazareth*.csv'))
        # files = glob.glob(os.path.join(DATA_DIR, '*.xlsx'))
        
        if not files:
            print(f"No Excel or CSV files found in {DATA_DIR}")
            return

        print(f"Found {len(files)} files to process.")

        for file_path in files:
            try:
                station_name = os.path.basename(file_path).split('.')[0]
                print(f"Processing: {station_name}")

                # Read File
                if file_path.endswith('.xlsx'):
                    df = pd.read_excel(file_path, header=2, na_values=["NoData", "-", ""])
                else:
                    # Try UTF-8, fallback to Hebrew encoding if needed
                    try:
                        df = pd.read_csv(file_path, header=0, na_values=["NoData", "-", ""])
                    except UnicodeDecodeError:
                        df = pd.read_csv(file_path, header=0, na_values=["NoData", "-", ""], encoding='ISO-8859-8')

                # Smart Unit Dropping (Detects if first row contains units like 'mm')
                try:
                    first_row_values = df.iloc[0].astype(str).values.tolist()
                    unit_keywords = ['mm', 'deg', 'm/sec', 'degc', 'hpa']
                    if any(keyword in str(val).lower() for val in first_row_values for keyword in unit_keywords):
                        print("   Detected units row. Dropping it.")
                        df = df.iloc[1:].reset_index(drop=True)
                except:
                    pass

                # Clean column names
                df.columns = df.columns.str.strip().str.lower().str.replace(r'[\s\(\)]+', '_', regex=True).str.strip('_')

                # Timestamp Handling
                if 'date' in df.columns and 'time' in df.columns:
                    # Handle 24:00 format in excel
                    mask_24 = df['time'].astype(str).str.contains('24:00')
                    df.loc[mask_24, 'time'] = '00:00'

                    # Legacy Excel Format (Split columns)
                    df['timestamp'] = pd.to_datetime(df['date'].astype(str) + ' ' + df['time'].astype(str), dayfirst=True, errors='coerce')
                    
                    # Add one day to match 00:00 as start of next day not prior day
                    if mask_24.any():
                        df.loc[mask_24, 'timestamp'] += pd.Timedelta(days=1)
                    
                    df = df.drop(columns=['date', 'time'])

                    # Force it to be Israel Standard Time then convert to UTC
                    df['timestamp'] = df['timestamp'].dt.tz_localize('Etc/GMT-2').dt.tz_convert('UTC')
                    
                    initial_count = len(df)
                    df = df.dropna(subset=['timestamp'])
                    if len(df) < initial_count:
                        print(f"   Dropped {initial_count - len(df)} rows due to invalid timestamps.")

                elif 'timestamp' in df.columns:
                    # API CSV Format (Single column)
                    df['timestamp'] = pd.to_datetime(df['timestamp'], utc=True, errors='coerce')
                    df = df.dropna(subset=['timestamp'])
                
                garbage_cols = [
                        'time', 'time.1', 'vbatt', 'id', 'stab', 
                        'heatstresscalc', 'dewpointcalc', 'coldstresscalc', 'bp'
                ]
                df = df.drop(columns=garbage_cols, errors='ignore')

                # Station ID Logic
                if 'station_id' in df.columns:
                    df['station_id'] = pd.to_numeric(df['station_id'], errors='coerce')
                
                elif any(station_name.startswith(k) for k in STATION_MAP):
                    match = next(k for k in STATION_MAP if station_name.startswith(k))
                    print(f"   Mapped '{station_name}' to ID {STATION_MAP[match]}")
                    df['station_id'] = STATION_MAP[match]
                
                else:
                    print(f"Error: Could not determine Station ID for '{station_name}'. Skipping.")
                    continue

                # Type Enforcement
                dtype_mapping = {
                    'timestamp': types.DateTime(),
                    'station_id': types.Integer()
                }
                
                numeric_cols = [col for col in df.columns if col not in ['timestamp', 'station_id']]
                for col in numeric_cols:
                    df[col] = pd.to_numeric(df[col], errors='coerce')
                    dtype_mapping[col] = types.Float

                # Reorder columns
                cols = ['timestamp', 'station_id'] + numeric_cols
                df = df[cols]

                # Upload with Chunking (Prevent memory crash)
                df.to_sql(
                    TABLE_NAME,
                    engine,
                    if_exists='append',
                    index=False,
                    dtype=dtype_mapping, # type: ignore
                    method=insert_on_conflict_nothing,
                    chunksize=2000
                )
                print(f"Success: {station_name}")

            except Exception as e:
                print(f"Error processing {file_path}: {e}")

    except Exception as e:
        print(f"Critical Database Error: {e}")

if __name__ == "__main__":
    ingest_data()