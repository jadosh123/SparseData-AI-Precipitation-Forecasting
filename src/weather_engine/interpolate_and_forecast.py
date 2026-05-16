"""
Offline inference — skips IMS fetching and cleaning.

Reads clean_station_data as-is, runs cell interpolation and forecasting,
then replaces cell_forecasts. Useful for backtesting or manual runs where
clean_station_data is already populated.
"""

import pandas as pd
import xgboost as xgb
from datetime import datetime, timezone, timedelta
from sqlalchemy import text

from weather_engine.database import engine
from weather_engine.cell_interpolation import load_cell_features
from weather_engine.cell_forecasting import make_inference_features
from weather_engine.utils import encode_time_features, get_project_root


UPSTREAM_STATION_IDS = {178, 43}  # Tel Aviv, Haifa


def load_interpolation_models() -> dict[str, xgb.Booster]:
    models_dir = get_project_root() / "models" / "spatial_interpolation"
    models = {}
    for path in models_dir.glob("*.json"):
        feature = path.stem.split("xgb_")[1]
        m = xgb.Booster()
        m.load_model(path)
        models[feature] = m
    return models


def load_forecast_models() -> dict[str, xgb.Booster]:
    models_dir = get_project_root() / "models" / "single_point"
    models = {}
    for path in models_dir.glob("*.json"):
        _, step = path.stem.split("xgb_")[1].split("+")
        m = xgb.Booster()
        m.load_model(path)
        models[f"precipitation_t{step}"] = m
    return models


def interpolate_and_store(cell_neighbors: pd.DataFrame, station_frames: dict, models: dict) -> None:
    total = len(cell_neighbors)
    print(f"\n--- Interpolation: {total} cells, {len(models)} features each ---")

    records = []
    for i, (_, row) in enumerate(cell_neighbors.iterrows(), 1):
        cell_id = int(row['cell_id'])
        neighbor_ids = [int(row['neighbor_1_id']), int(row['neighbor_2_id']), int(row['neighbor_3_id'])]

        if not all(nid in station_frames for nid in neighbor_ids):
            print(f"  [{i}/{total}] Cell {cell_id}: missing neighbor data, skipping.")
            continue

        X = load_cell_features(
            row['elevation'], row['dist_to_coast'],
            int(row['neighbor_1_id']), int(row['neighbor_2_id']), int(row['neighbor_3_id']),
            row['neighbor_1_distance'], row['neighbor_2_distance'], row['neighbor_3_distance'],
            station_frames=station_frames
        )
        X = encode_time_features(X)
        current_hour = datetime.now(timezone.utc).replace(tzinfo=None, minute=0, second=0, microsecond=0)
        X = X[X.index < current_hour]

        if X.empty:
            print(f"  [{i}/{total}] Cell {cell_id}: no rows after filtering, skipping.")
            continue

        print(f"  [{i}/{total}] Cell {cell_id}: interpolating {len(X)} timestamps "
              f"({X.index[0]} → {X.index[-1]})")

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
        from sqlalchemy.dialects.sqlite import insert as sqlite_insert

        def _insert_ignore(table, conn, keys, data_iter):
            conn.execute(sqlite_insert(table.table).values(list(data_iter)).on_conflict_do_nothing())

        total_rows = sum(len(r) for r in records)
        print(f"\nWriting {total_rows} interpolated rows to cell_interpolated...")
        pd.concat(records).to_sql('cell_interpolated', engine, if_exists='append', index=False, method=_insert_ignore, chunksize=10_000)

    print("Interpolation complete.")


def forecast_and_store(cell_neighbors: pd.DataFrame, station_frames: dict, models: dict) -> None:
    total = len(cell_neighbors)
    print(f"\n--- Forecasting: {total} cells, horizons: {list(models.keys())} ---")

    upstream_dfs = {
        "tel_aviv": station_frames[178],
        "haifa": station_frames[43],
    }

    records = []
    for i, (_, row) in enumerate(cell_neighbors.iterrows(), 1):
        cell_id = int(row['cell_id'])
        df_target = pd.read_sql(
            "SELECT * FROM cell_interpolated WHERE cell_id = :cid",
            engine, params={'cid': cell_id}
        )
        df_target['timestamp'] = pd.to_datetime(df_target['timestamp'])
        df_target = df_target.drop(columns=['cell_id']).set_index('timestamp').sort_index()

        X = make_inference_features(df_target, upstream_dfs)
        if X.empty:
            print(f"  [{i}/{total}] Cell {cell_id}: not enough data for lag features, skipping.")
            continue

        print(f"  [{i}/{total}] Cell {cell_id}: forecasting {len(X)} timestamps "
              f"({X.index[0]} → {X.index[-1]})")

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
    total_rows = len(forecasts)

    print(f"\nReplacing cell_forecasts with {total_rows} rows...")
    with engine.begin() as conn:
        conn.execute(text("DELETE FROM cell_forecasts"))

    forecasts.to_sql('cell_forecasts', engine, if_exists='append', index=False)
    print(f"Done. {total_rows} forecast rows written.")


def main() -> None:
    start = datetime.now(timezone.utc).replace(tzinfo=None)
    print(f"[{start.isoformat()}] interpolate_and_forecast starting...")

    print("\nLoading clean_station_data...")
    all_clean = pd.read_sql("SELECT * FROM clean_station_data", engine)
    all_clean['timestamp'] = pd.to_datetime(all_clean['timestamp'])
    all_clean = all_clean.set_index('timestamp').sort_index()
    station_frames = {sid: grp.drop(columns='station_id')
                      for sid, grp in all_clean.groupby('station_id')}
    print(f"  {len(station_frames)} stations loaded, "
          f"{len(all_clean)} total rows, "
          f"{all_clean.index.min()} → {all_clean.index.max()}")

    print("\nLoading models...")
    cell_neighbors = pd.read_sql("SELECT * FROM cell_neighbors", engine)
    interp_models = load_interpolation_models()
    forecast_models = load_forecast_models()
    print(f"  {len(interp_models)} interpolation models: {list(interp_models.keys())}")
    print(f"  {len(forecast_models)} forecast models: {list(forecast_models.keys())}")
    print(f"  {len(cell_neighbors)} cells in cell_neighbors")

    interpolate_and_store(cell_neighbors, station_frames, interp_models)
    forecast_and_store(cell_neighbors, station_frames, forecast_models)

    elapsed = (datetime.now(timezone.utc).replace(tzinfo=None) - start).total_seconds()
    print(f"\n[{datetime.now(timezone.utc).replace(tzinfo=None).isoformat()}] Done in {elapsed:.1f}s")


if __name__ == "__main__":
    main()
