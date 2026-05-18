"""
One-off script to populate station_metadata with terrain features by hitting
only the lightweight /stations endpoint — no re-fetching of historical data.
Assumes station_metadata has already been cleared (DROP + CREATE in init.sql).
"""
import sys
import pandas as pd

from weather_engine.fetch_ims_data import fetch_location_data
from weather_engine.database import engine
from weather_engine.utils import get_elevation_from_hgt, get_distance_to_coast


def main():
    print("Fetching station locations from IMS API...")
    location_map = fetch_location_data()

    if not location_map:
        print("No stations returned. Check API key / network.")
        sys.exit(1)

    print(f"Got {len(location_map)} stations. Computing terrain features...")
    rows = []
    for i, (station_id, meta) in enumerate(location_map.items(), 1):
        lat = meta.get('lat')
        lon = meta.get('lon')

        if not lat or not lon:
            print(f"  [{i}/{len(location_map)}] Station {station_id}: no coordinates, skipping.")
            continue

        terrain = get_elevation_from_hgt(lat, lon)
        dist = get_distance_to_coast(lat, lon)

        rows.append({
            'station_id':         int(station_id),
            'latitude':           lat,
            'longitude':          lon,
            'elevation':          terrain['elevation'],
            'tpi_local':          terrain['tpi_local'],
            'tpi_regional':       terrain['tpi_regional'],
            'roughness_local':    terrain['roughness_local'],
            'roughness_regional': terrain['roughness_regional'],
            'dist_to_coast':      dist,
        })
        print(f"  [{i}/{len(location_map)}] Station {station_id} ({meta.get('name')}): "
              f"elev={terrain['elevation']}, tpi_local={terrain['tpi_local'] if terrain['tpi_local'] else 'N/A'}")

    df = pd.DataFrame(rows)
    df.to_sql('station_metadata', engine, if_exists='append', index=False)
    print(f"\nWrote {len(df)} stations to station_metadata.")


if __name__ == "__main__":
    main()
