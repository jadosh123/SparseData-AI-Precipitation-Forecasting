import requests
import csv
import os
import time
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv

# --- Configuration ---
base_dir = Path(__file__).resolve().parent.parent
env_file = base_dir / '.env'

# 2. Load the file
load_dotenv(env_file)

# 3. Fetch the key securely
API_KEY = os.getenv("API_KEY")
BASE_URL = "https://api.ims.gov.il/v1/envista/stations"

# Update this with your actual station IDs
# Example: {ID: "Name"}
STATIONS = {
    # 16: "Afula_Nir_HaEmek", 
    # 13: "Tavor_Kadoorie", 
    # 186: "Newe_Yaar", 
    500: "Nazareth"
}

START_YEAR = 2020
END_YEAR = 2025

# Save directly to the folder that syncs with Docker
OUTPUT_DIR = os.path.expanduser("/app/cloud_data")

# The headers match your DB schema exactly
CSV_HEADERS = [
    'timestamp', 'station_id', 'rain', 'wsmax', 'wdmax', 'ws', 'wd',
    'stdwd', 'td', 'rh', 'tdmax', 'tdmin', 'ws1mm', 'ws10mm',
    'time', 'vbatt', 'id', 'stab', 'heatstresscalc', 'dewpointcalc',
    'coldstresscalc', 'bp'
]

# Mapping JSON names to DB Columns
CHANNEL_MAP = {
    'rain': 'rain', 'wsmax': 'wsmax', 'wdmax': 'wdmax', 'ws': 'ws',
    'wd': 'wd', 'stdwd': 'stdwd', 'td': 'td', 'rh': 'rh',
    'tdmax': 'tdmax', 'tdmin': 'tdmin', 'ws1mm': 'ws1mm',
    'ws10mm': 'ws10mm', 'time': 'time', 'vbatt': 'vbatt',
    'id': 'id', 'stab': 'stab', 'heatstresscalc': 'heatstresscalc',
    'dewpointcalc': 'dewpointcalc', 'coldstresscalc': 'coldstresscalc',
    'bp': 'bp'
}

def fetch_yearly_data(station_id, year):
    """Fetches data with Retries and User-Agent spoofing."""
    from_date = f"{year}/01/01"
    to_date = f"{year + 1}/01/01"
    url = f"{BASE_URL}/{station_id}/data?from={from_date}&to={to_date}"
    
    # 1. Add User-Agent to look like a real browser/Postman
    headers = {
        "Authorization": f"ApiToken {API_KEY}",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
    }
    
    print(f"   ⬇️ Fetching {year}...", end="\r")
    
    # 2. Retry Logic (Try 3 times before giving up)
    for attempt in range(3):
        try:
            response = requests.get(url, headers=headers, timeout=60) # Increased timeout
            
            # If successful, parse JSON
            if response.status_code == 200:
                return response.json()
            
            # If server error (500+), wait and retry
            elif response.status_code >= 500:
                print(f"   ⚠️ Server error {response.status_code}. Retrying ({attempt+1}/3)...")
                time.sleep(5)
                continue
                
            # If client error (400/401/403/404), stop immediately
            else:
                print(f"\n   ❌ Client Error {response.status_code}: {response.text[:100]}")
                return None

        except requests.exceptions.JSONDecodeError:
            # This catches the "Expecting value..." error
            print(f"\n   ❌ Failed to decode JSON. Server returned: {response.text[:200]}...")
            return None
            
        except Exception as e:
            print(f"\n   ⚠️ Network error: {e}. Retrying...")
            time.sleep(5)

    print(f"\n   ❌ Failed after 3 attempts.")
    return None

def process_observation(obs, station_id):
    """Flattens a single JSON observation into a CSV row dict."""
    row = {h: None for h in CSV_HEADERS}
    row['timestamp'] = obs.get('datetime') # ISO Format matches Postgres
    row['station_id'] = station_id
    
    for channel in obs.get('channels', []):
        if channel.get('valid'):
            name = channel.get('name', '').lower()
            # Map API name to DB column
            if name in CHANNEL_MAP:
                row[CHANNEL_MAP[name]] = channel.get('value')
    return row

def main():
    if not os.path.exists(OUTPUT_DIR):
        print(f"Creating output directory: {OUTPUT_DIR}")
        os.makedirs(OUTPUT_DIR, exist_ok=True)

    print(f"🚀 Starting Data Fetch for {len(STATIONS)} stations...")

    for station_id, station_name in STATIONS.items():
        filename = f"{station_name}_{START_YEAR}-{END_YEAR}.csv"
        filepath = os.path.join(OUTPUT_DIR, filename)
        
        print(f"\n📡 Station: {station_name} (ID: {station_id})")
        print(f"   💾 Saving to: {filepath}")

        # Open file ONCE per station (Write mode)
        with open(filepath, 'w', newline='', encoding='utf-8') as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=CSV_HEADERS)
            writer.writeheader() # Write CSV header row 1

            total_rows = 0
            for year in range(START_YEAR, END_YEAR):
                data = fetch_yearly_data(station_id, year)
                
                if data and 'data' in data:
                    rows = []
                    for obs in data['data']:
                        rows.append(process_observation(obs, station_id))
                    
                    if rows:
                        writer.writerows(rows) # Write this year's chunk immediately
                        total_rows += len(rows)
                
                # Be polite to the API
                time.sleep(1)
            
            print(f"\n   ✅ Finished {station_name}: {total_rows} rows saved.")

    print("\n🏁 All downloads complete.")

if __name__ == "__main__":
    main()