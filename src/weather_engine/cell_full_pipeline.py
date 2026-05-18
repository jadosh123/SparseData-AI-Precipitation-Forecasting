from weather_engine.database import engine
import xgboost as xgb
from pathlib import Path
import pandas as pd
from weather_engine.cell_interpolation import load_cell_features
from weather_engine.utils import get_project_root, encode_time_features
from weather_engine.cell_forecasting import make_inference_features


ROOT = get_project_root()

def load_model_paths() -> tuple[list[Path], list[Path]]:
    models_dir = ROOT / "models"
    models_forecast_dir = models_dir / "single_point"
    models_interpolate_dir = models_dir / "spatial_interpolation"

    models_forecast = list(models_forecast_dir.glob("*.json"))
    models_interpolate = list(models_interpolate_dir.glob("*.json"))

    return models_forecast, models_interpolate


def load_station_frames() -> dict[int, pd.DataFrame]:
    all_data = pd.read_sql("SELECT * FROM clean_station_data", engine)
    all_data['timestamp'] = pd.to_datetime(all_data['timestamp'])

    all_data = all_data.set_index('timestamp').sort_index()
    station_frames = {sid: grp.drop(columns='station_id') 
                    for sid, grp in all_data.groupby('station_id')}

    return station_frames


def load_models(model_paths: list[Path], model_type: str) -> dict[str, xgb.Booster]:
    models = {}
    for model_path in model_paths:
        if model_type == "interpolate":
            feature = model_path.stem.split("xgb_")[1]
        else:
            _, step = model_path.stem.split("xgb_")[1].split("+")
            feature = f"precipitation_t{step}"
            
        m = xgb.Booster()
        m.load_model(model_path)
        models[feature] = m

    return models


def interpolate_cells(
    cell_neighbors: pd.DataFrame,
    station_frames: dict[int, pd.DataFrame],
    models: dict[str, xgb.Booster]
) -> None:
    records = []

    for _, row in cell_neighbors.iterrows():
        cell_terrain = {col: row[col] for col in ('tpi_local', 'tpi_regional', 'roughness_local', 'roughness_regional')}
        X = load_cell_features(
            row['elevation'],
            row['dist_to_coast'],
            int(row['neighbor_1_id']),
            int(row['neighbor_2_id']),
            int(row['neighbor_3_id']),
            row['neighbor_1_distance'],
            row['neighbor_2_distance'],
            row['neighbor_3_distance'],
            station_frames=station_frames,
            cell_terrain=cell_terrain,
        )
        X = encode_time_features(X)

        record = {'cell_id': int(row['cell_id']), 'timestamp': X.index}
        for feature, model in models.items():
            preds = model.predict(xgb.DMatrix(X[model.feature_names]))
            if feature in ('rain', 'ws', 'rh'):
                preds = preds.clip(0)
            if feature == 'rh':
                preds = preds.clip(0, 100)
            record[feature] = preds

        records.append(pd.DataFrame(record))

    interpolated = pd.concat(records)
    interpolated.to_sql("cell_interpolated", engine, if_exists="append", index=False)


def forecast_cells(
    cell_neighbors: pd.DataFrame,
    station_frames: dict[int, pd.DataFrame],
    models: dict[str, xgb.Booster]
) -> None:
    upstream_dfs = {
        "tel_aviv": station_frames[178],
        "haifa": station_frames[43],
    }
    records = []

    for _, row in cell_neighbors.iterrows():
        cell_id = int(row['cell_id'])
        df_target = pd.read_sql(
            "SELECT * FROM cell_interpolated WHERE cell_id = :cid",
            engine, params={'cid': cell_id},
        )
        df_target['timestamp'] = pd.to_datetime(df_target['timestamp'])
        df_target = df_target.drop(columns=['cell_id']).set_index('timestamp').sort_index()

        X = make_inference_features(df_target, upstream_dfs)

        record = {'cell_id': cell_id, 'timestamp': X.index}
        for key, model in models.items():
            record[key] = model.predict(xgb.DMatrix(X[model.feature_names])).clip(0)

        records.append(pd.DataFrame(record))

    forecasts = pd.concat(records)
    forecasts.to_sql("cell_forecasts", engine, if_exists="append", index=False)


def main() -> None:
    print("Loading cell neighbors and station frames...")
    cell_neighbors = pd.read_sql("SELECT * FROM cell_neighbors", engine)
    station_frames = load_station_frames()
    print(f"Loaded {len(cell_neighbors)} cells, {len(station_frames)} station frames.")

    print("Loading models...")
    models_forecast_paths, models_interpolate_paths = load_model_paths()
    models_forecast = load_models(models_forecast_paths, "forecast")
    models_interpolate = load_models(models_interpolate_paths, "interpolate")
    print(f"Loaded {len(models_interpolate)} interpolation models, {len(models_forecast)} forecast models.")

    print("Running interpolation...")
    interpolate_cells(cell_neighbors, station_frames, models_interpolate)
    print("Interpolation complete.")
    
    print("Running forecasting...")
    forecast_cells(cell_neighbors, station_frames, models_forecast)
    print("Forecasting complete.")


if __name__ == "__main__":
    main()