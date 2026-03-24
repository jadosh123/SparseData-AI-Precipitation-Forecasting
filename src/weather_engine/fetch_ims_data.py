import requests
import csv
import os
import json
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
DISCORD_WEBHOOK = os.getenv("DISCORD_WEBHOOK")

START_YEAR = 2020
END_YEAR = 2026
OUTPUT_DIR = Path("/app/cloud_data")

LOG_PATH = Path("logs/")

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

def send_discord_alert(message: str) -> None:
    """
    Sends discord alerts to configured webhook regarding failed data fetching.
    """
    data = {'content': message}
    try:
        requests.post(DISCORD_WEBHOOK, json=data)
    except:
        pass

def fetch_yearly_data(station_id, year):
    """Fetches weather station data with retries and User-Agent data."""

    date_intervals = []
    for month in range(1, 13):
        start_date = f"{year}/{month:02d}/01"

        if month != 12:
            end_date = f"{year}/{month + 1:02d}/01"
        else:
            end_date = f"{year + 1}/01/01"

        date_intervals.append((start_date, end_date))
    
    headers = {
        "Authorization": f"ApiToken {API_KEY}",
        "User-Agent": "MyWeatherApp/1.0 (Contact: jadosh2000@gmail.com)"
    }
    
    print(f"Fetching {year}...")
    all_observations = []

    start_time = datetime.now()
    for start_date, end_date in date_intervals:
        url = f"{BASE_URL}/{station_id}/data?from={start_date}&to={end_date}"

        month_success = False
        for attempt in range(5):
            try:
                response = requests.get(url, headers=headers, timeout=60)
                
                if response.status_code == 200:
                    data_json = response.json()
                    if data_json and 'data' in data_json:
                        all_observations.extend(data_json['data'])
                    month_success = True
                    print(f"Fetched data for {start_date} to {end_date}")
                    break

                elif response.status_code in [429, 500, 502, 503, 504]:
                    wait_time = 15 + (attempt * 15)
                    msg = f"Status {response.status_code} for station {station_id}. Retrying in {wait_time}s..."
                    print(msg)
                    with open(LOG_PATH / "network_responses.log", "a", encoding="utf-8") as log:
                        log.write(f"{datetime.now()}: {msg}\n")
                    time.sleep(wait_time)  # Aggressive backoff (15s, 30s, 45s, 60s)
                    continue
                
                elif response.status_code == 204:
                    print("No Content (204). Station might be inactive this month.")
                    month_success = True
                    break

                else:
                    msg = f"Client Error {response.status_code} for station {station_id}: {response.text[:100]}"
                    print(f"\n{msg}")
                    with open(LOG_PATH / "network_responses.log", "a", encoding="utf-8") as log:
                        log.write(f"{datetime.now()}: {msg}\n")

            except requests.exceptions.RequestException as e:
                # Network level errors (Connection Refused, Timeout, Empty HTTP pages)
                wait_time = 15 + (attempt * 15)
                msg = f"Network Error ({e}) for station {station_id}. Retrying in {wait_time}s..."
                print(msg)
                with open(LOG_PATH / "network_responses.log", "a", encoding="utf-8") as log:
                    log.write(f"{datetime.now()}: {msg}\n")
                time.sleep(wait_time)
        
        # Breather between requests
        time.sleep(10)

        if not month_success:
            fail_msg = f"Failed after 5 attempts for station {station_id} (year {year}) (date {start_date})."
            print(f"\n{fail_msg}")
            send_discord_alert(fail_msg)
            with open(LOG_PATH / "network_responses.log", "a", encoding="utf-8") as log:
                log.write(f"{datetime.now()}: {fail_msg}\n")

    end_time = datetime.now()
    print(f"Data fetching took: {end_time - start_time}")
    return {'data': all_observations} if all_observations else None

def fetch_location_data() -> dict[int, dict[str, str | float]]:
    """Fetches latitude and longitude data, caching to a file."""
    cache_file = LOG_PATH / "stations_and_locations.json"
    
    try:
        if cache_file.exists():
            print(f"Loading location map from {cache_file}...", end="\r")
            with open(cache_file, "r", encoding="utf-8") as f:
                data = json.load(f)
        else:
            headers = {
                "Authorization": f"ApiToken {API_KEY}",
                "User-Agent": "MyWeatherApp/1.0 (Contact: jadosh2000@gmail.com)"
            }
            print(f"Fetching location map from API...", end="\r")
            
            # We hit the base /stations endpoint to get the full list
            response = requests.get(BASE_URL, headers=headers, timeout=60)
            response.raise_for_status()
            data_temp = response.json()
            
            data = []

            # Filter for relevant station names
            for s in data_temp:
                if any(char.isdigit() for char in s.get('name')):
                    continue
                else:
                    data.append(s)

            # Save it for next time
            with open(cache_file, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=4)
                
        # Convert list to a fast lookup dictionary
        meta_map = {}
        for s in data:
            sid = s.get('stationId')
            loc = s.get('location', {})
            meta_map[sid] = {
                'name': s.get('name'),
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
    if not OUTPUT_DIR.exists():
        print(f"Creating output directory: {OUTPUT_DIR}")
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    
    LOG_PATH.mkdir(parents=True, exist_ok=True)
        
    location_map = fetch_location_data()

    # Checkpoint logic to not refetch station data
    processed_stations = set()
    fp = LOG_PATH / "fetch_stats.csv"
    
    # Load all previously finished station IDs into a fast Python set
    if fp.exists():
        with open(fp, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                processed_stations.add(int(row['station_id']))
    print(f"Starting Data Fetch for {len(location_map)} stations... ({len(processed_stations)} already done!)")

    for station_id, station_loc in location_map.items():

        if int(station_id) in processed_stations:
            print(f"Station ID {station_id} already exists in CSV logs. Skipping...")
            continue

        name = station_loc.get('name')
        station_name = str(name).replace(' ', '_')
        
        filename = f"{station_name}_{START_YEAR}-{END_YEAR}.csv"
        filepath = OUTPUT_DIR / filename
        
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
                time.sleep(15)
            
            success_msg = f"Finished {station_name}: {total_rows} rows saved."
            print(f"\n{success_msg}")

            fp = LOG_PATH / "fetch_stats.csv"
            file_exists = fp.exists()

            with open(fp, "a", newline='', encoding="utf-8") as csv_log:
                csv_headers = ['station_name', 'station_id', 'total_rows']
                writer = csv.DictWriter(csv_log, csv_headers)

                if not file_exists:
                    writer.writeheader()

                writer.writerow({
                    'station_name': station_loc.get('name'),
                    'station_id': station_id,
                    'total_rows': total_rows
                })

    print("\nAll downloads complete.")
    send_discord_alert("✅ All 84 stations have been downloaded successfully!")

if __name__ == "__main__":
    main()