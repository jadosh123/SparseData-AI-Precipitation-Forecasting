"""
Generates demo_snapshot.json by running the interpolation + forecasting pipeline
in-memory for the demo window. No DB writes — all intermediate data stays in RAM.
"""

import json
import pandas as pd
import xgboost as xgb
from sqlalchemy import create_engine
from weather_engine.utils import get_project_root, encode_time_features
from weather_engine.cell_interpolation import load_cell_features
from weather_engine.cell_forecasting import make_inference_features
from weather_engine.inference_pipeline import load_interpolation_models, load_forecast_models

ROOT = get_project_root()
engine = create_engine(f"sqlite:///{ROOT}/data/weather.db")

DEMO_START = "2024-12-27 05:00:00"
DEMO_END = "2024-12-27 23:00:00"
LAG_BUFFER = "2024-12-26 05:00:00"  # 24h before DEMO_START for lag features

print("Loading station frames...")
all_data = pd.read_sql(
    f"SELECT * FROM clean_station_data WHERE timestamp >= '{LAG_BUFFER}' AND timestamp <= '{DEMO_END}'",
    engine,
)
all_data['timestamp'] = pd.to_datetime(all_data['timestamp'])
all_data = all_data.set_index('timestamp').sort_index()
station_frames = {sid: grp.drop(columns='station_id') for sid, grp in all_data.groupby('station_id')}

cell_neighbors = pd.read_sql("SELECT * FROM cell_neighbors", engine)
print(f"Loaded {len(station_frames)} station frames, {len(cell_neighbors)} cells.")

print("Loading models...")
interp_models = load_interpolation_models()
forecast_models = load_forecast_models()

print("Running interpolation...")
interp_by_cell: dict[int, pd.DataFrame] = {}
for _, row in cell_neighbors.iterrows():
    cell_terrain = {col: row[col] for col in ('tpi_local', 'tpi_regional', 'roughness_local', 'roughness_regional')}
    X = load_cell_features(
        row['elevation'], row['dist_to_coast'],
        int(row['neighbor_1_id']), int(row['neighbor_2_id']), int(row['neighbor_3_id']),
        row['neighbor_1_distance'], row['neighbor_2_distance'], row['neighbor_3_distance'],
        station_frames=station_frames,
        cell_terrain=cell_terrain,
    )
    X = encode_time_features(X)

    interp = pd.DataFrame(index=X.index)
    for feature, model in interp_models.items():
        preds = model.predict(xgb.DMatrix(X[model.feature_names]))
        if feature in ('rain', 'ws', 'rh'):
            preds = preds.clip(0)
        if feature == 'rh':
            preds = preds.clip(0, 100)
        interp[feature] = preds

    interp_by_cell[int(row['cell_id'])] = interp

print("Running forecasting...")
upstream_dfs = {"tel_aviv": station_frames[178], "haifa": station_frames[43]}
lat_map = cell_neighbors.set_index('cell_id')['lat']
lon_map = cell_neighbors.set_index('cell_id')['lon']
records = []

for _, row in cell_neighbors.iterrows():
    cell_id = int(row['cell_id'])
    df_target = interp_by_cell[cell_id]
    X = make_inference_features(df_target, upstream_dfs)
    X = X[(X.index >= DEMO_START) & (X.index <= DEMO_END)]
    if X.empty:
        continue

    record = pd.DataFrame({'cell_id': cell_id, 'timestamp': X.index.astype(str)})
    for key, model in forecast_models.items():
        record[key] = model.predict(xgb.DMatrix(X[model.feature_names])).clip(0)
    record['lat'] = lat_map[cell_id]
    record['lon'] = lon_map[cell_id]
    records.append(record)

rows = pd.concat(records).to_dict(orient='records')

out_path = ROOT / "src" / "weather_engine" / "demo_snapshot" / "demo_snapshot.json"
with open(out_path, "w") as f:
    json.dump(rows, f, indent=2)

print(f"Wrote {len(rows)} rows to {out_path}")
