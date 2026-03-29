from pathlib import Path
import math
import pandas as pd
import rasterio

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
        
    hgt_dir = get_project_root() / 'data' / 'SRTMGL1_003-20260321_112154'
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
