import re
import pandas as pd
import numpy as np
from weather_engine.database import engine


def single_station_load(station_id: int) -> pd.DataFrame:
    query = "SELECT * FROM clean_station_data WHERE station_id=:sid"
    return pd.read_sql(query, engine, params={'sid': station_id})


def sort_by_ts(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df['timestamp'] = pd.to_datetime(df['timestamp'], errors='coerce')
    df.set_index('timestamp', inplace=True)
    df.sort_index(axis=0, ascending=True, inplace=True)
    return df


def create_local_lags(df: pd.DataFrame, lag_hours=[1, 2, 3, 6, 12, 24], target_lag: int = 1) -> pd.DataFrame:
    df_out = df.copy()
    target_cols = ['rain', 'u_vec', 'v_vec', 'td', 'rh' ]

    for col in target_cols:
        if col in df_out.columns:
            for h in lag_hours:
                df_out[f"{col}_t-{h}h"] = df_out[col].shift(h)

    df_out[f'target_rain_t+{target_lag}'] = df_out['rain'].shift(-target_lag)
    return df_out


def add_upstream_features(
    df_target: pd.DataFrame,
    df_upstream: pd.DataFrame,
    upstream_name: str,
    lag_hours=[1, 2, 3],
    join_type='left'
) -> pd.DataFrame:
    force_cols = ['rain', 'u_vec', 'v_vec', 'rh']
    renamed_cols = {c: f"{c}_{upstream_name}" for c in force_cols}
    df_force = df_upstream[force_cols].rename(columns=renamed_cols).reindex(df_target.index)

    df_force[f"u_convergence_{upstream_name}"] = df_force[f"u_vec_{upstream_name}"] - df_target["u_vec"]
    df_force[f"v_convergence_{upstream_name}"] = df_force[f"v_vec_{upstream_name}"] - df_target["v_vec"]
    df_force[f"moisture_flux_{upstream_name}"] = df_force[f"u_vec_{upstream_name}"] * df_force[f"rh_{upstream_name}"]

    for col in list(df_force.columns):
        for h in lag_hours:
            df_force[f"{col}_t-{h}h"] = df_force[col].shift(h)

    return df_target.join(df_force, how=join_type)


def get_constraints(df: pd.DataFrame, target_pattern: str = r't\+\d+') -> dict:
    rain_keywords = ['rain', 'convergence', 'moisture_flux', 'rh']
    negative_keywords = ['td', 'tdmax']
    constraints = {}

    for col in df.columns:
        if re.search(target_pattern, col):
            continue
        if any(kw in col for kw in negative_keywords):
            constraints[col] = -1
        if any(kw in col for kw in rain_keywords):
            constraints[col] = 1

    return constraints


def temporal_split(df: pd.DataFrame, target_col: str, val_start_date: str, test_start_date: str):
    feature_cols = [c for c in df.columns if c != target_col]
    X = df[feature_cols]
    y = df[target_col]

    X_train = X[X.index < val_start_date]
    y_train = y[y.index < val_start_date]

    mask_val = (X.index >= val_start_date) & (X.index < test_start_date)
    X_val, y_val = X[mask_val], y[mask_val]

    X_test = X[X.index >= test_start_date]
    y_test = y[y.index >= test_start_date]

    return X_train, X_val, X_test, y_train, y_val, y_test


def create_production_backbone(raw_start_str: str, raw_end_str: str, max_lag_hours: int, freq='h') -> pd.DataFrame:
    t0 = pd.Timestamp(raw_start_str)
    tend = pd.Timestamp(raw_end_str)
    effective_start = t0 + pd.Timedelta(hours=max_lag_hours)

    master_index = pd.date_range(start=effective_start, end=tend, freq=freq)
    df_master = pd.DataFrame(index=master_index)
    df_master.index.name = 'timestamp'
    return df_master


def prepare_dataset(df: pd.DataFrame, target_lag: int = 1, max_lag: int = 24) -> pd.DataFrame:
    df_lagged = create_local_lags(df, target_lag=target_lag)
    df_trimmed = df_lagged.iloc[max_lag:]
    return df_trimmed.dropna(subset=[f'target_rain_t+{target_lag}'])


def make_single_point_features(
    target_station_id: int,
    upstream_station_ids: dict,
    target_lags: list = [1, 3, 6, 12],
    max_lag_hours: int = 24,
    raw_start_str: str = "2020-01-01 00:00:00",
    raw_end_str: str = "2026-01-01 00:00:00",
    val_start_date: str = "2024-01-01",
    test_start_date: str = "2025-01-01",
) -> tuple[dict, dict, dict]:
    """
    Full feature engineering pipeline for single-point precipitation forecasting.

    :param target_station_id: Station ID to forecast for.
    :param upstream_station_ids: Dict mapping upstream name -> station_id. e.g. {"tel_aviv": 178, "haifa": 43}
    :param target_lags: List of forecast horizons in hours.
    :param max_lag_hours: Maximum lag depth used for feature creation and warm-up trimming.
    :param raw_start_str: Start of the raw data range.
    :param raw_end_str: End of the raw data range.
    :param val_start_date: Start date for validation split.
    :param test_start_date: Start date for test split.

    :returns: (datasets, constraints_dict, test_sets)
        - datasets[lag]: fully engineered DataFrame for each horizon
        - constraints_dict[lag]: monotonicity constraints for each horizon
        - test_sets[lag]: dict with X_train, X_val, X_test, y_train, y_val, y_test
    """
    df_target = sort_by_ts(single_station_load(target_station_id))

    upstream_dfs = {}
    for name, sid in upstream_station_ids.items():
        upstream_dfs[name] = sort_by_ts(single_station_load(sid))

    df_backbone = create_production_backbone(raw_start_str, raw_end_str, max_lag_hours)

    datasets = {}
    constraints_dict = {}
    test_sets = {}

    for lag in target_lags:
        target_col = f'target_rain_t+{lag}'

        df_lagged = prepare_dataset(df_target, target_lag=lag, max_lag=max_lag_hours)
        df_lagged = df_backbone.join(df_lagged, how='left').dropna(subset=[target_col])

        for name, df_up in upstream_dfs.items():
            df_lagged = add_upstream_features(df_lagged, df_up, upstream_name=name, join_type='left')

        datasets[lag] = df_lagged
        constraints_dict[lag] = get_constraints(df_lagged)

        X_train, X_val, X_test, y_train, y_val, y_test = temporal_split(
            df_lagged, target_col, val_start_date, test_start_date
        )
        test_sets[lag] = {
            'X_train': X_train, 'X_val': X_val, 'X_test': X_test,
            'y_train': y_train, 'y_val': y_val, 'y_test': y_test
        }

        print(f"[t+{lag}h] shape={df_lagged.shape}, train={len(X_train)}, val={len(X_val)}, test={len(X_test)}")

    return datasets, constraints_dict, test_sets


if __name__ == "__main__":
    datasets, constraints_dict, test_sets = make_single_point_features(
        target_station_id=16,
        upstream_station_ids={"tel_aviv": 178, "haifa": 43},
    )
