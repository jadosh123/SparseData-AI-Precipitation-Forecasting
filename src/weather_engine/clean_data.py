from pathlib import Path
from dotenv import load_dotenv
import pandas as pd
import numpy as np
from sqlalchemy import types
from weather_engine.database import engine

base_dir = Path(__file__).resolve().parent.parent
env_file = base_dir / '.env'
load_dotenv(env_file)

# DB_CONN_STR = os.getenv("DB_CONN_STR")
SOURCE_TABLE = "raw_station_data"
TARGET_TABLE = "clean_station_data"

def get_wind_components(ws, wd):
    """
    Converts Wind Speed (m/s) and Direction (deg) into U and V vectors.
    """
    # Northerly winds 0 deg -> South (Negative)
    # Easterly winds 90 deg -> West (Negative)
    # Southerly winds 180 deg -> North (Positive)
    # Westerly winds 270 deg -> East (Positive)

    wd_rad = np.deg2rad(wd)
    u = -ws * np.sin(wd_rad) # X axis
    v = -ws * np.cos(wd_rad) # Y axis
    return u, v

def clean_station_data():
    print(f"Reading from {SOURCE_TABLE}...")
    try:
        station_ids = pd.read_sql(f"SELECT DISTINCT station_id FROM {SOURCE_TABLE}", engine)['station_id'].tolist()
    except ValueError:
        print(f"Error: Table {SOURCE_TABLE} not found or empty.")
        return

    dtype_mapping = {
        'timestamp': types.DateTime(),
        'station_id': types.Integer(),
        'rain': types.Float(),
        'td': types.Float(),
        'u_vec': types.Float(),
        'v_vec': types.Float()
    }

    # cols in bronze layer
    # ['timestamp', 'rain', 'ws', 'wd', 'stdwd', 'td', 'rh', 'tdmax', 'tdmin', 'station_id']
    agg_rules = {
        'rain': 'sum',
        'ws': 'mean',
        'stdwd': 'mean',
        'td': 'mean',
        'rh': 'mean',
        'tdmax': 'max',
        'tdmin': 'min',
        'u_vec': 'mean',
        'v_vec': 'mean'
    }

    for i, station_id in enumerate(station_ids):
        print(f"Processing station {station_id} ({i + 1}/{len(station_ids)})...")
        df = pd.read_sql(f"SELECT * FROM {SOURCE_TABLE} WHERE station_id = {station_id}", engine)

        df['timestamp'] = pd.to_datetime(df['timestamp'], utc=True)

        cols_to_check = ['rain', 'ws', 'wd', 'stdwd', 'td', 'rh', 'tdmax', 'tdmin']
        high_miss = [c for c in cols_to_check if c in df.columns and df[c].isna().mean() > 0.30]
        if high_miss:
            print(f"  Skipping station {station_id}: >30% missing in {high_miss}.")
            del df
            continue

        df['rain'] = df['rain'].where(df['rain'] >= 0, other=np.nan)
        df['u_vec'], df['v_vec'] = get_wind_components(df['ws'], df['wd'])
        df = df.set_index('timestamp').sort_index()

        valid_agg = {k: v for k, v in agg_rules.items() if k in df.columns}
        hourly = df.resample('1h').agg(valid_agg) # type: ignore
        hourly = hourly.interpolate(method='linear', limit=2)
        hourly.loc[hourly['td'] > hourly['tdmax'], 'tdmax'] = hourly['td']
        hourly.loc[hourly['td'] < hourly['tdmin'], 'tdmin'] = hourly['td']
        hourly['station_id'] = station_id

        hourly.reset_index().to_sql(
            TARGET_TABLE,
            engine,
            if_exists='replace' if i == 0 else 'append',
            index=False,
            dtype=dtype_mapping,
            chunksize=5000
        )
        del df, hourly

    print("Data Cleaning Complete.")

if __name__ == "__main__":
    clean_station_data()