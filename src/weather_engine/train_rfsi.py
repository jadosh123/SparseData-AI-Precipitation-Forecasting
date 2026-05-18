"""One-time script to retrain RFSI models with Afula (station 16) included in the neighbor pool."""

import pandas as pd
import xgboost as xgb
from sklearn.metrics import mean_absolute_error, root_mean_squared_error
from pathlib import Path

from weather_engine.database import engine
from weather_engine.llocv import load_fold, temporal_split_fold
from weather_engine.utils import encode_time_features, get_project_root

FEATURES = ['rain', 'ws', 'td', 'rh', 'tdmax', 'tdmin', 'u_vec', 'v_vec']
TERRAIN_FEATURES = {'rain', 'ws', 'rh'}
TERRAIN_COLS = [f'{c}_{suffix}'
                for c in ('tpi_local', 'tpi_regional', 'roughness_local', 'roughness_regional')
                for suffix in ('target', 'n1', 'n2', 'n3')]
# Station 500 (Nazareth) stays excluded — insufficient data, causes regression
EXCLUDED_STATIONS = {500}


def build_dataset() -> tuple[pd.DataFrame, pd.DataFrame]:
    station_neighbors: pd.DataFrame = pd.read_sql("SELECT * FROM station_neighbors", engine)

    # Drop Nazareth from pool (permanent exclusion — not Afula)
    station_neighbors = station_neighbors[
        ~station_neighbors[["station_id", "neighbor_1_id", "neighbor_2_id", "neighbor_3_id"]]
        .isin(EXCLUDED_STATIONS).any(axis=1)
    ].reset_index(drop=True)

    all_data = pd.read_sql("SELECT * FROM clean_station_data", engine)
    all_data['timestamp'] = pd.to_datetime(all_data['timestamp'])
    all_data = all_data.set_index('timestamp').sort_index()
    station_frames = {sid: grp.drop(columns='station_id')
                      for sid, grp in all_data.groupby('station_id')}

    all_X, all_y = [], []
    for _, row in station_neighbors.iterrows():
        X, y = load_fold(
            int(row["station_id"]),
            int(row["neighbor_1_id"]),
            int(row["neighbor_2_id"]),
            int(row["neighbor_3_id"]),
            station_frames=station_frames
        )
        all_X.append(X)
        all_y.append(y)

    print(f"Loaded {len(all_X)} station folds.")

    all_X = encode_time_features(pd.concat(all_X).sort_index())
    all_y = pd.concat(all_y).sort_index()
    return all_X, all_y


def train(all_X: pd.DataFrame, all_y: pd.DataFrame) -> dict:
    X_train, X_val, y_train, y_val = temporal_split_fold(all_X, all_y)

    models = {}
    for i, feature in enumerate(FEATURES, 1):
        print(f"[{i}/{len(FEATURES)}] Training RFSI for '{feature}'...", end=' ', flush=True)
        drop_cols = [] if feature in TERRAIN_FEATURES else [c for c in TERRAIN_COLS if c in X_train.columns]
        X_tr = X_train.drop(columns=drop_cols)
        X_vl = X_val.drop(columns=drop_cols)

        if feature == 'rain':
            model = xgb.XGBRegressor(n_jobs=-1, objective='reg:tweedie', tweedie_variance_power=1.5)
        else:
            model = xgb.XGBRegressor(n_jobs=-1, objective='reg:squarederror')

        model.fit(X_tr, y_train[feature])
        preds = model.predict(X_vl)
        mae = mean_absolute_error(y_val[feature], preds)
        rmse = root_mean_squared_error(y_val[feature], preds)
        print(f"MAE={mae:.4f}  RMSE={rmse:.4f}")
        models[feature] = model

    return models


def save_models(models: dict) -> None:
    save_dir = get_project_root() / "models" / "spatial_interpolation"
    save_dir.mkdir(parents=True, exist_ok=True)
    for feature, model in models.items():
        path = save_dir / f"xgb_{feature}.json"
        model.get_booster().save_model(path)
        print(f"Saved {path}")


if __name__ == "__main__":
    print("Building dataset (Afula included, Nazareth excluded)...")
    all_X, all_y = build_dataset()
    print("Training RFSI models...")
    models = train(all_X, all_y)
    print("Saving models...")
    save_models(models)
    print("Done. Models written to models/spatial_interpolation/")
