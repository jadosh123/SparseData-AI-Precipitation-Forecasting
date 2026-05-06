import pandas as pd
from weather_engine.utils import encode_time_features


def create_local_lags(df: pd.DataFrame, lag_hours=[1, 2, 3, 6, 12, 24]) -> pd.DataFrame:
    df_out = df.copy()
    target_cols = ['rain', 'u_vec', 'v_vec', 'td', 'rh']

    for col in target_cols:
        if col in df_out.columns:
            for h in lag_hours:
                df_out[f"{col}_t-{h}h"] = df_out[col].shift(h)

    return df_out


def add_upstream_features(
    df_target: pd.DataFrame,
    df_upstream: pd.DataFrame,
    upstream_name: str,
    lag_hours=[1, 2, 3],
    join_type='left',
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


def make_inference_features(
    df_target: pd.DataFrame,
    upstream_dfs: dict,
    max_lag_hours: int = 24,
) -> pd.DataFrame:
    """
    Builds the inference feature matrix for a single cell across all forecast horizons.

    :param df_target: Interpolated cell DataFrame indexed by timestamp.
    :param upstream_dfs: Dict mapping upstream name -> DataFrame indexed by timestamp.
    :param max_lag_hours: Lag depth used for feature creation; first max_lag_hours rows are dropped.
    :returns: Feature matrix X ready for model.predict.
    """
    df = encode_time_features(df_target.copy())
    df = create_local_lags(df)
    df = df.iloc[max_lag_hours:].dropna()

    for name, df_up in upstream_dfs.items():
        df = add_upstream_features(df, df_up, upstream_name=name)

    return df
