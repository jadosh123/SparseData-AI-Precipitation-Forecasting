from pathlib import Path
import rasterio
import math
import pandas as pd
import numpy as np
import h5py

def get_project_root() -> Path:
    """
    Finds and returns the project root by traversing upwards from the current 
    file's directory until a .toml file (such as pyproject.toml) is found.
    
    Returns:
        Path: The absolute path to the project's root directory.
        
    Raises:
        FileNotFoundError: If the root of the file system is reached without finding a .toml file.
    """
    current_path = Path(__file__).resolve().parent
    
    while current_path != current_path.parent:
        # Check if there are any .toml files in the current directory
        if list(current_path.glob("*.toml")):
            return current_path
            
        # Move up one level
        current_path = current_path.parent
        
    raise FileNotFoundError("Could not find the project root (no .toml file found in any parent directories).")

def get_elevation_from_hgt(lat, lon):
    """Uses rasterio to pinpoint a latitude/longitude and extract its exact elevation from the .hgt tile."""

    if pd.isna(lat) or pd.isna(lon):
        return None
        
    hgt_dir = get_project_root() / 'data' / 'elevation_data'
    lat_prefix = 'N' if lat >= 0 else 'S'
    lon_prefix = 'E' if lon >= 0 else 'W'
    
    lat_int = math.floor(abs(lat))
    lon_int = math.floor(abs(lon))
    
    tile_name = f"{lat_prefix}{lat_int:02d}{lon_prefix}{lon_int:03d}.hgt"
    tile_path = hgt_dir / tile_name
    
    if not tile_path.exists():
        return None
        
    try:
        with rasterio.open(tile_path) as src:
            for val in src.sample([(lon, lat)]):
                elev = val[0]
                if int(elev) == -32768:  # SRTM NoData
                    return None
                return float(elev)
    except Exception as e:
        print(f"Error reading {tile_name}: {e}")
        return None
    
def get_distance_to_coast(lat, lon) -> float | None:
    """Samples the GSHHG distance-to-coast NetCDF grid at the given lat/lon and returns distance in km."""
    if pd.isna(lat) or pd.isna(lon):
        return None

    nc_path = get_project_root() / 'data' / 'dist_to_GSHHG_v2.3.7_1m.nc'
    if not nc_path.exists():
        return None

    try:
        with h5py.File(nc_path, 'r') as f:
            lats = f['lat'][:]
            lons = f['lon'][:]
            lat_idx = int(np.argmin(np.abs(lats - lat)))
            lon_idx = int(np.argmin(np.abs(lons - lon)))
            dist = float(f['dist'][lat_idx, lon_idx])
        return dist
    except Exception as e:
        print(f"Error reading distance to coast: {e}")
        return None


def encode_time_features(df: pd.DataFrame) -> pd.DataFrame:
    if 'timestamp' in df.columns:
        ts = pd.to_datetime(df['timestamp']).dt.tz_localize('UTC').dt.tz_convert('Asia/Jerusalem')
    else:
        ts = pd.Series(df.index.tz_localize('UTC').tz_convert('Asia/Jerusalem'), index=df.index)
  
    month = ts.dt.month
    df['month_sin'] = np.sin(2 * np.pi * month / 12)
    df['month_cos'] = np.cos(2 * np.pi * month / 12)
    
    day = ts.dt.day_of_year
    df['day_sin'] = np.sin(2 * np.pi * day / ts.dt.is_leap_year.map({True: 366, False: 365}))
    df['day_cos'] = np.cos(2 * np.pi * day / ts.dt.is_leap_year.map({True: 366, False: 365}))
    
    return df