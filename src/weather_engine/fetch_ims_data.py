import requests
import csv
import os
import time
import math
import rasterio
import utils as ut
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv

# Configuration
base_dir = ut.get_project_root()
env_file = base_dir / '.env'
load_dotenv(env_file)

API_KEY = os.getenv("API_KEY")
BASE_URL = "https://api.ims.gov.il/v1/envista/stations"

STATIONS = {
    16: "Afula_Nir_HaEmek", 
    13: "Tavor_Kadoorie", 
    186: "Newe_Yaar", 
    500: "Nazareth_City",
    43: "Haifa_Technion",
    178: "TelAviv_Coast",
    263: "Galed",
    380: "Tel_Yosef",
    67: "En_Hashofet"
}

START_YEAR = 2020
END_YEAR = 2026
OUTPUT_DIR = "/app/cloud_data"

CSV_HEADERS = [
    'timestamp', 
    'station_id',
    'latitude',
    'longitude', 
    'elevation',
    'rain', 
    'wsmax', 
    'wdmax', 
    'ws', 
    'wd',
    'stdwd', 
    'td', 
    'rh', 
    'tdmax', 
    'tdmin', 
    'ws1mm', 
    'ws10mm',
]

CHANNEL_MAP = {
    'rain': 'rain',
    'wsmax': 'wsmax',
    'wdmax': 'wdmax',
    'ws': 'ws',
    'wd': 'wd',
    'stdwd': 'stdwd',
    'td': 'td',
    'rh': 'rh',
    'tdmax': 'tdmax',
    'tdmin': 'tdmin',
    'ws1mm': 'ws1mm',
    'ws10mm': 'ws10mm',
}

def fetch_yearly_data(station_id, year):
    """Fetches weather station data with retries and User-Agent spoofing."""
    from_date = f"{year}/01/01"
    to_date = f"{year + 1}/01/01"
    url = f"{BASE_URL}/{station_id}/data?from={from_date}&to={to_date}"
    
    headers = {
        "Authorization": f"ApiToken {API_KEY}",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
    }
    
    print(f"Fetching {year}...")
    
    for attempt in range(5):
        try:
            response = requests.get(url, headers=headers, timeout=60)
            
            if response.status_code == 200:
                time.sleep(30)
                return response.json()
            
            elif response.status_code in [429, 500, 502, 503, 504]:
                wait_time = 15 + (attempt * 15)
                print(f"Status {response.status_code}. Retrying in {wait_time}s...")
                time.sleep(wait_time) # Aggressive backoff (15s, 30s, 45s, 60s)
                continue
            
            elif response.status_code == 204:
                print("No Content (204). Station might be inactive this year.")
                return None
            else:
                print(f"\nClient Error {response.status_code}: {response.text[:100]}")
                return None

        except requests.exceptions.RequestException as e:
            # Network level errors (Connection Refused, Timeout, Empty HTTP pages)
            wait_time = 15 + (attempt * 15)
            print(f"Network Error ({e}). Retrying in {wait_time}s...")
            time.sleep(wait_time)

    print(f"\nFailed after 5 attempts.")
    return None

def fetch_location_data():
    """Fetches latitude and longitude data with retries and User-Agent spoofing."""

    headers = {
        "Authorization": f"ApiToken {API_KEY}",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
    }
    
    print(f"Fetching location map...", end="\r")
    
    try:
        # We hit the base /stations endpoint to get the full list
        response = requests.get(BASE_URL, headers=headers, timeout=60)
        response.raise_for_status()
        data = response.json()
        
        # Convert list to a fast lookup dictionary
        meta_map = {}
        for s in data:
            sid = s.get('stationId')
            loc = s.get('location', {})
            meta_map[sid] = {
                'lat': loc.get('latitude'),
                'lon': loc.get('longitude')
            }
        print("Metadata map built successfully.")
        return meta_map

    except Exception as e:
        print(f"\nError fetching metadata: {e}")
        return {}

def get_elevation_from_hgt(lat, lon):
    """Uses rasterio to pinpoint a latitude/longitude and extract its exact elevation from the .hgt tile."""
    if not lat or not lon:
        return None
        
    hgt_dir = base_dir / 'data' / 'SRTMGL1_003-20260321_112154'
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

def process_observation(obs, station_id, lat, lon, elev):
    """Flattens a single JSON observation into a CSV row dict."""
    row = {h: None for h in CSV_HEADERS}
    row['timestamp'] = obs.get('datetime')
    row['station_id'] = station_id
    row['latitude'] = lat
    row['longitude'] = lon
    row['elevation'] = elev
    
    for channel in obs.get('channels', []):
        if channel.get('valid'):
            name = channel.get('name', '').lower()
            if name in CHANNEL_MAP:
                row[CHANNEL_MAP[name]] = channel.get('value')
    return row

def main():
    if not os.path.exists(OUTPUT_DIR):
        print(f"Creating output directory: {OUTPUT_DIR}")
        os.makedirs(OUTPUT_DIR, exist_ok=True)
        
    location_map = fetch_location_data()

    print(f"Starting Data Fetch for {len(STATIONS)} stations...")

    for station_id, station_name in STATIONS.items():
        filename = f"{station_name}_{START_YEAR}-{END_YEAR}.csv"
        filepath = os.path.join(OUTPUT_DIR, filename)
        
        station_loc = location_map.get(station_id, {})
        lat = station_loc.get('lat')
        lon = station_loc.get('lon')
        elev = get_elevation_from_hgt(lat, lon)
        
        if not lat or not lon:
            print(f"Warning: No coordinates found for Station {station_id}. CSV will have empty Lat/Lon.")
        
        print(f"\nStation: {station_name} (ID: {station_id})")
        print(f"Saving to: {filepath}")

        with open(filepath, 'w', newline='', encoding='utf-8') as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=CSV_HEADERS)
            writer.writeheader()

            total_rows = 0
            for year in range(START_YEAR, END_YEAR):
                data = fetch_yearly_data(station_id, year)
                
                if data and 'data' in data:
                    rows = []
                    for obs in data['data']:
                        rows.append(process_observation(obs, station_id, lat, lon, elev))
                    
                    if rows:
                        writer.writerows(rows)
                        total_rows += len(rows)
                
                # Big delay between hitting the server for a new year of data
                time.sleep(30)
            
            print(f"\nFinished {station_name}: {total_rows} rows saved.")

    print("\nAll downloads complete.")

if __name__ == "__main__":
    main()