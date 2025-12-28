from pathlib import Path
from dotenv import load_dotenv
import pandas as pd
import numpy as np
import os
from sqlalchemy import create_engine, types


base_dir = Path(__file__).resolve().parent.parent
env_file = base_dir / '.env'
load_dotenv(env_file)
db_user = os.getenv("POSTGRES_USER")
db_pass = os.getenv("POSTGRES_PASSWORD")
db_host = os.getenv("DB_HOST")
db_name = os.getenv("POSTGRES_DB")

DB_CONN_STR = f"postgresql+psycopg2://{db_user}:{db_pass}@{db_host}:5432/{db_name}"
SOURCE_TABLE = "raw_station_data"
TARGET_TABLE = "clean_station_data"

def get_wind_components(ws, wd):
    """
    Converts Wind Speed (m/s) and Direction (deg) into U and V vectors.
    """
    wd_rad = np.deg2rad(wd)
    u = -ws * np.sin(wd_rad) # X axis
    v = -ws * np.cos(wd_rad) # Y axis
    return u, v

def clean_station_data():
    engine = create_engine(DB_CONN_STR)
    df = pd.read_sql_table(SOURCE_TABLE, engine)
    
    df['timestamp'] = pd.to_datetime(df["timestamp"], utc=True)
    df = df.sort_values(['station_id', 'timestamp'])
    
    clean_dfs = []
    for station_id, group in df.groupby('station_id'):
        group['u_vec'], group['v_vec'] = get_wind_components(group['ws'], group['wd'])
        group = group.set_index('timestamp').sort_index()
        
        # cols in bronze layer
        # ['timestamp', 'rain', 'wsmax', 'wdmax', 'ws', 'wd', 'stdwd', 'td', 'rh', 'tdmax', 'tdmin', 'ws1mm', 'ws10mm', 'station_id']
        agg_rules = {
            'rain': 'sum',
            'wsmax': 'max',
            'wdmax': 'max',
            'ws': 'mean',
            'stdwd': 'mean',
            'td': 'mean',
            'rh': 'mean',
            'tdmax': 'max',
            'tdmin': 'min',
            'ws1mm': 'max',
            'ws10mm': 'max',
            'u_vec': 'mean',
            'v_vec': 'mean'
        }
        
        # Grabbing first lat and lon from unclean station data
        try:
            lat = group['latitude'].dropna().iloc[0]
            lon = group['longitude'].dropna().iloc[0]
        except IndexError:
            print(f"Warning: No Lat/Lon found for Station {station_id}. Using 0.0.")
            lat, lon = 0.0, 0.0

        
        # Filter to only use cols present in the data
        valid_agg = {k: v for k, v in agg_rules.items() if k in group.columns}
        
        hourly = group.resample('1h').agg(valid_agg) # type: ignore

        # Capturing max rain intensity in a 10-min segment for storm identification
        hourly['rain_intensity_max'] = group['rain'].resample('1h').max()
        hourly = hourly.interpolate(method='linear', limit=2)
        
        hourly['station_id'] = station_id
        hourly['latitude'] = lat
        hourly['longitude'] = lon
        clean_dfs.append(hourly)

    print("Merging cleaned data.")
    final_df = pd.concat(clean_dfs).reset_index()
    print(f"Saving {len(final_df)} hourly rows to '{TARGET_TABLE}'.")
    
    dtype_mapping = {
        'timestamp': types.DateTime(),
        'station_id': types.Integer(),
        'rain': types.Float(),
        'td': types.Float(),
        'u_vec': types.Float(),
        'v_vec': types.Float(),
        'latitude': types.Float(),
        'longitude': types.Float()
    }
    
    final_df.to_sql(
        TARGET_TABLE, 
        engine, 
        if_exists='replace',
        index=False,
        dtype=dtype_mapping, # type: ignore
        chunksize=5000
    )
    
    print("Data Cleaning Complete.") 

if __name__ == "__main__":
    clean_station_data()