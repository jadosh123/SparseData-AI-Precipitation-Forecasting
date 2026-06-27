import json
import os
import time
import requests
import numpy as np
import pandas as pd
import xgboost as xgb
from datetime import datetime, timedelta, timezone
from sqlalchemy import text, types
from sqlalchemy.dialects.sqlite import insert as sqlite_insert

from weather_engine.database import engine
from weather_engine.cell_interpolation import load_cell_features
from weather_engine.cell_forecasting import make_inference_features
from weather_engine.utils import encode_time_features, get_project_root, send_discord_alert
from weather_engine.fetch_ims_data import process_observation
from weather_engine.map_builder import build_and_cache_live_maps

from dotenv import load_dotenv
load_dotenv(get_project_root() / '.env')

API_KEY = os.getenv("API_KEY")
BASE_URL = "https://api.ims.gov.il/v1/envista/stations"
WINDOW_HOURS = 27
UPSTREAM_STATION_IDS = {178, 43}  # Tel Aviv, Haifa — hardcoded to match forecasting models

DTYPE_RAW = {
    'timestamp': types.DateTime(),
    'station_id': types.Integer(),
    'rain': types.Float(),
    'ws': types.Float(),
    'wd': types.Float(),
    'td': types.Float(),
    'rh': types.Float(),
    'tdmax': types.Float(),
    'tdmin': types.Float(),
}

DTYPE_CLEAN = {
    'timestamp': types.DateTime(),
    'station_id': types.Integer(),
    'rain': types.Float(),
    'ws': types.Float(),
    'td': types.Float(),
    'rh': types.Float(),
    'tdmax': types.Float(),
    'tdmin': types.Float(),
    'u_vec': types.Float(),
    'v_vec': types.Float(),
}


def _insert_ignore(table, conn, keys, data_iter) -> None:  # type: ignore[no-untyped-def]
    conn.execute(sqlite_insert(table.table).values(list(data_iter)).on_conflict_do_nothing())


def get_required_station_ids() -> set[int]:
    """Returns neighbor station IDs from cell_neighbors plus hardcoded upstream stations."""
    cn = pd.read_sql("SELECT neighbor_1_id, neighbor_2_id, neighbor_3_id FROM cell_neighbors", engine)
    neighbor_ids = set(cn[['neighbor_1_id', 'neighbor_2_id', 'neighbor_3_id']].values.flatten().tolist())
    return neighbor_ids | UPSTREAM_STATION_IDS


def fetch_station_range(station_id: int, lat: float, lon: float) -> list[dict]:
    """Fetches 2 days back through today using the range endpoint (IMS date = UTC+2, `to` is exclusive)."""
    headers = {
        "Authorization": f"ApiToken {API_KEY}",
        "User-Agent": "MyWeatherApp/1.0 (Contact: jadosh2000@gmail.com)"
    }
    # IMS dates are always in UTC+2 regardless of season
    ist_now = datetime.now(timezone.utc) + timedelta(hours=2)
    from_date = (ist_now - timedelta(days=2)).strftime("%Y/%m/%d")
    to_date = (ist_now + timedelta(days=1)).strftime("%Y/%m/%d")  # exclusive upper bound

    url = f"{BASE_URL}/{station_id}/data?from={from_date}&to={to_date}"
    for attempt in range(5):
        try:
            resp = requests.get(url, headers=headers, timeout=60)
            if resp.status_code == 200:
                if not resp.content:
                    return []
                return [process_observation(obs, station_id, lat, lon) for obs in resp.json().get('data', [])]
            elif resp.status_code == 204:
                return []
            elif resp.status_code in [429, 500, 502, 503, 504]:
                wait = 30 + attempt * 30
                print(f"  Station {station_id}: status {resp.status_code}, retrying in {wait}s (attempt {attempt+1}/5)")
                time.sleep(wait)
        except requests.exceptions.RequestException as e:
            wait = 30 + attempt * 30
            print(f"  Station {station_id}: network error {e}, retrying in {wait}s (attempt {attempt+1}/5)")
            time.sleep(wait)

    send_discord_alert(f"[inference_pipeline] Failed to fetch station {station_id} after 5 attempts.")
    return []


COLD_START_DIR = get_project_root() / "src" / "weather_engine" / "cold_start"


def load_cold_start_json(filename: str) -> list[dict]:
    with open(COLD_START_DIR / filename) as f:
        return json.load(f)


def bootstrap_static_tables() -> None:
    meta_count = pd.read_sql("SELECT COUNT(*) as n FROM station_metadata", engine)['n'].iloc[0]
    if meta_count == 0:
        records = load_cold_start_json("station_metadata.json")
        pd.DataFrame(records).to_sql('station_metadata', engine, if_exists='append', index=False)
        print(f"Bootstrapped station_metadata with {len(records)} rows.")

    cell_count = pd.read_sql("SELECT COUNT(*) as n FROM cell_neighbors", engine)['n'].iloc[0]
    if cell_count == 0:
        records = load_cold_start_json("cell_neighbors.json")
        pd.DataFrame(records).to_sql('cell_neighbors', engine, if_exists='append', index=False)
        print(f"Bootstrapped cell_neighbors with {len(records)} rows.")


def fetch_and_store_raw(station_ids: set[int]) -> pd.DataFrame | None:
    print(f"Fetching {len(station_ids)} stations (yesterday + today)...")

    meta_df = pd.read_sql("SELECT station_id, latitude, longitude FROM station_metadata", engine)
    coords: dict[int, tuple[float, float]] = {
        int(r['station_id']): (float(r['latitude']), float(r['longitude']))
        for _, r in meta_df.iterrows()
    }

    all_rows = []
    for sid in station_ids:
        if sid not in coords:
            print(f"  Skipping station {sid}: no coordinates in station_metadata.")
            continue
        lat, lon = coords[sid]
        print(f"  Fetching station {sid}...")
        rows = fetch_station_range(sid, lat, lon)
        print(f"  Station {sid}: {len(rows)} rows")
        all_rows.extend(rows)
        time.sleep(2)

    if not all_rows:
        print("No new rows fetched.")
        return None

    # Data processing
    df = pd.DataFrame(all_rows)
    df['timestamp'] = pd.DatetimeIndex(pd.to_datetime(df['timestamp'].astype(str).str.replace(r'[+-]\d{2}:\d{2}$', '', regex=True), errors='coerce')) - pd.Timedelta(hours=2)
    df = df.drop(columns=['latitude', 'longitude', 'wsmax', 'wdmax', 'stdwd', 'ws1mm', 'ws10mm'], errors='ignore')
    numeric_cols = [c for c in df.columns if c not in ('timestamp', 'station_id')]
    for col in numeric_cols:
        df[col] = pd.to_numeric(df[col], errors='coerce')

    df.to_sql('raw_station_data', engine, if_exists='append', index=False,
              dtype=DTYPE_RAW, method=_insert_ignore, chunksize=500)  # type: ignore[arg-type]

    print(f"Stored {len(df)} raw rows.")
    return df


def get_wind_components(ws, wd):
    wd_rad = np.deg2rad(wd)
    return -ws * np.sin(wd_rad), -ws * np.cos(wd_rad)


def clean_and_store(df_raw: pd.DataFrame) -> None:
    print("Cleaning raw data...")

    latest_clean = pd.read_sql(
        "SELECT MAX(timestamp) as latest FROM clean_station_data", engine
    )['latest'].iloc[0]

    agg_rules = {
        'rain': 'sum', 'ws': 'mean', 'td': 'mean',
        'rh': 'mean', 'tdmax': 'max', 'tdmin': 'min',
        'u_vec': 'mean', 'v_vec': 'mean'
    }

    for sid, df in df_raw.groupby('station_id'):
        if latest_clean is not None:
            df = df[df['timestamp'] > pd.Timestamp(latest_clean)]
        if df.empty:
            continue
        
        df['timestamp'] = pd.to_datetime(df['timestamp'])
        df['rain'] = df['rain'].where(df['rain'] >= 0, other=np.nan)
        df['ws'] = pd.to_numeric(df['ws'], errors='coerce')
        df['wd'] = pd.to_numeric(df['wd'], errors='coerce')
        df['u_vec'], df['v_vec'] = get_wind_components(df['ws'], df['wd'])
        df = df.set_index('timestamp').sort_index()

        valid_agg = {k: v for k, v in agg_rules.items() if k in df.columns}
        hourly = df.resample('1h').agg(valid_agg)  # type: ignore[arg-type]
        hourly = hourly.interpolate(method='linear', limit=2)
        hourly.loc[hourly['td'] > hourly['tdmax'], 'tdmax'] = hourly['td']
        hourly.loc[hourly['td'] < hourly['tdmin'], 'tdmin'] = hourly['td']
        hourly['station_id'] = sid

        hourly.reset_index().to_sql(
            'clean_station_data', engine, if_exists='append',
            index=False, dtype=DTYPE_CLEAN, chunksize=500, method=_insert_ignore  # type: ignore[arg-type]
        )

    # Trim to rolling window
    with engine.begin() as conn:
        conn.execute(text(
            "DELETE FROM clean_station_data WHERE timestamp < :cutoff"
        ), {'cutoff': datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(hours=WINDOW_HOURS)})

    print("Clean step complete.")


def load_interpolation_models() -> dict[str, xgb.Booster]:
    models_dir = get_project_root() / "models" / "spatial_interpolation"
    models = {}
    for path in models_dir.glob("*.json"):
        feature = path.stem.split("xgb_")[1]
        m = xgb.Booster()
        m.load_model(path)
        models[feature] = m
    return models


def interpolate_and_store(cell_neighbors: pd.DataFrame, station_frames: dict, models: dict) -> None:
    print("Interpolating cells...")

    records = []
    for _, row in cell_neighbors.iterrows():
        cell_id = int(row['cell_id'])
        neighbor_ids = [int(row['neighbor_1_id']), int(row['neighbor_2_id']), int(row['neighbor_3_id'])]

        if not all(nid in station_frames for nid in neighbor_ids):
            print(f"Cell {cell_id}: missing neighbor data, skipping.")
            continue
        
        cell_terrain = {col: row[col] for col in ('tpi_local', 'tpi_regional', 'roughness_local', 'roughness_regional')}
        X = load_cell_features(
            row['elevation'], row['dist_to_coast'],
            int(row['neighbor_1_id']), int(row['neighbor_2_id']), int(row['neighbor_3_id']),
            row['neighbor_1_distance'], row['neighbor_2_distance'], row['neighbor_3_distance'],
            station_frames=station_frames,
            cell_terrain=cell_terrain,
        )
        X = encode_time_features(X)
        current_hour = datetime.now(timezone.utc).replace(tzinfo=None, minute=0, second=0, microsecond=0)
        X = X[X.index < current_hour]

        if X.empty:
            continue

        record = {'cell_id': cell_id, 'timestamp': X.index}
        for feature, model in models.items():
            preds = model.predict(xgb.DMatrix(X[model.feature_names]))
            if feature in ('rain', 'ws', 'rh'):
                preds = preds.clip(0)
            if feature == 'rh':
                preds = preds.clip(0, 100)
            if feature == 'rain':
                preds[preds < 0.01] = 0.0
            record[feature] = preds

        records.append(pd.DataFrame(record))

    if records:
        pd.concat(records).to_sql('cell_interpolated', engine, if_exists='append', index=False, chunksize=500, method=_insert_ignore)  # type: ignore[arg-type]

    # Trim to rolling window
    with engine.begin() as conn:
        conn.execute(text(
            "DELETE FROM cell_interpolated WHERE timestamp < :cutoff"
        ), {'cutoff': datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(hours=WINDOW_HOURS)})

    print("Interpolation complete.")


def load_forecast_models() -> dict[str, xgb.Booster]:
    models_dir = get_project_root() / "models" / "single_point"
    models = {}
    for path in models_dir.glob("*.json"):
        _, step = path.stem.split("xgb_")[1].split("+")
        m = xgb.Booster()
        m.load_model(path)
        models[f"precipitation_t{step}"] = m
    return models


def forecast_and_store(cell_neighbors: pd.DataFrame, station_frames: dict, models: dict) -> None:
    print("Forecasting cells...")

    upstream_dfs = {
        "tel_aviv": station_frames[178],
        "haifa": station_frames[43],
    }

    records = []
    for _, row in cell_neighbors.iterrows():
        cell_id = int(row['cell_id'])
        df_target = pd.read_sql(
            "SELECT * FROM cell_interpolated WHERE cell_id = :cid",
            engine, params={'cid': cell_id}
        )
        df_target['timestamp'] = pd.to_datetime(df_target['timestamp'])
        df_target = df_target.drop(columns=['cell_id']).set_index('timestamp').sort_index()

        X = make_inference_features(df_target, upstream_dfs)
        if X.empty:
            print(f"  Cell {cell_id}: not enough data for lag features, skipping.")
            continue

        # Take only the last row — current forecast
        X = X.iloc[[-1]]

        record = {'cell_id': cell_id, 'timestamp': X.index}
        for key, model in models.items():
            pred = model.predict(xgb.DMatrix(X[model.feature_names])).clip(0)
            pred[pred < 0.01] = 0.0
            record[key] = pred

        records.append(pd.DataFrame(record))

    if not records:
        print("No forecast records produced.")
        return

    forecasts = pd.concat(records)

    with engine.begin() as conn:  # type: ignore[reportUnreachable]
        conn.execute(text("DELETE FROM cell_forecasts"))

    forecasts.to_sql('cell_forecasts', engine, if_exists='append', index=False)
    print(f"Replaced cell_forecasts with {len(forecasts)} rows.")


def main() -> None:
    msg = f"[{datetime.now(timezone.utc).replace(tzinfo=None).isoformat()}] inference_pipeline starting..."
    print(msg)
    send_discord_alert(msg)

    bootstrap_static_tables()

    station_ids = get_required_station_ids()

    # Fetching and Cleaning
    df_raw = fetch_and_store_raw(station_ids)
    if df_raw is None:
        send_discord_alert("No new data was fetched.\nExiting inference pipeline...")
        return

    send_discord_alert(f"Fetched data from {len(station_ids)} stations.")
    clean_and_store(df_raw)
    send_discord_alert("Cleaned and aggregated data")

    # Load station frames from clean_station_data for interpolation + upstream
    all_clean = pd.read_sql("SELECT * FROM clean_station_data", engine)  # NEeds to get changed to use existing df in memory
    all_clean['timestamp'] = pd.to_datetime(all_clean['timestamp'])
    all_clean = all_clean.set_index('timestamp').sort_index()
    station_frames = {sid: grp.drop(columns='station_id')
                      for sid, grp in all_clean.groupby('station_id')}

    cell_neighbors = pd.read_sql("SELECT * FROM cell_neighbors", engine)
    interp_models = load_interpolation_models()
    forecast_models = load_forecast_models()
    
    send_discord_alert("Interpolating cells...")
    interpolate_and_store(cell_neighbors, station_frames, interp_models)
    send_discord_alert("Forecasting cells...")
    forecast_and_store(cell_neighbors, station_frames, forecast_models)
    send_discord_alert("Finished!")
    
    print("Building live map cache...")
    build_and_cache_live_maps()

    msg = f"[{datetime.now(timezone.utc).replace(tzinfo=None).isoformat()}] Pipeline complete."
    print(msg)
    send_discord_alert(msg)


if __name__ == "__main__":
    main()
