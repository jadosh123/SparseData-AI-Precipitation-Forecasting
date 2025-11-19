import pandas as pd
from sqlalchemy import create_engine, inspect, types
import time
import os
import glob

# Database connection string
DB_CONN_STR = "postgresql+psycopg2://myuser:mypassword@db:5432/weather_db"

# Path to the data directory
DATA_DIR = "/app/cloud_data/"
TABLE_NAME = "raw_station_data"

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

        excel_files = glob.glob(os.path.join(DATA_DIR, '*.xlsx'))
        if not excel_files:
            print(f"No Excel files found in {DATA_DIR}")
            return

        print(f"Found {len(excel_files)} Excel files to process.")

        for file_path in excel_files:
            try:
                station_name = os.path.basename(file_path).split('.')[0]
                print(f"Processing file: {file_path} for station: {station_name}")

                # 1. Read Excel with specific parameters
                df = pd.read_excel(
                    file_path,
                    header=2,  # Column names are on the 3rd row (0-indexed)
                    na_values=["NoData", "-", ""] # Handle custom null values
                )

                # 2. Drop the units row (which is now the first row of the DataFrame)
                df = df.iloc[1:].reset_index(drop=True)

                # 3. Clean column names
                df.columns = df.columns.str.strip().str.lower().str.replace(r'[\s\(\)]+', '_', regex=True).str.strip('_')

                # 4. Create timestamp column
                if 'date' in df.columns and 'time' in df.columns:
                    df['timestamp'] = pd.to_datetime(df['date'].astype(str) + ' ' + df['time'].astype(str), format='%d/%m/%Y %H:%M', errors='coerce')
                    df = df.drop(columns=['date', 'time'])
                else:
                    print(f"Warning: 'date' or 'time' column not found in {file_path}. Skipping timestamp creation.")
                    continue
                
                # 5. Add station name
                df['station_name'] = str(station_name)

                # 6. Force numeric types for all columns except timestamp and station_name
                dtype_mapping = {
                    'timestamp': types.DateTime(),
                    'station_name': types.String()
                }
                
                numeric_cols = [col for col in df.columns if col not in ['timestamp', 'station_name']]
                for col in numeric_cols:
                    df[col] = pd.to_numeric(df[col], errors='coerce')
                    dtype_mapping[col] = types.Float

                # Reorder columns to have timestamp and station_name first
                cols = ['timestamp', 'station_name'] + [col for col in df.columns if col not in ['timestamp', 'station_name']]
                df = df[cols]

                # 7. Upload to database
                df.to_sql(
                    TABLE_NAME,
                    engine,
                    if_exists='append',
                    index=False,
                    dtype=dtype_mapping
                )

                print(f"Successfully ingested data from {file_path} into {TABLE_NAME}")

            except Exception as e:
                print(f"An error occurred while processing {file_path}: {e}")

    except Exception as e:
        print(f"A general error occurred: {e}")

if __name__ == "__main__":
    ingest_data()