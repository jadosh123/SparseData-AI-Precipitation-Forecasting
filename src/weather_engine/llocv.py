from weather_engine.database import engine
import pandas as pd

def load_fold(
    target_id: int,
    neighbor_1_id: int,
    neighbor_2_id: int,
    neighbor_3_id: int,
    station_frames: dict | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    Loads a single LLOCV fold: target station as labels (y), neighbors as inputs (X).

    For each feature, the neighbor values at the same timestamp become the input
    columns and the target station value becomes the label. Rows where any of the
    4 stations has a null value are dropped.

    :param target_id: Station ID of the held-out target.
    :param neighbor_1_id: Station ID of first neighbor.
    :param neighbor_2_id: Station ID of second neighbor.
    :param neighbor_3_id: Station ID of third neighbor.
    :returns: (X, y) where X is the neighbor feature matrix and y is the target labels.
    """
    neighbor_ids = [neighbor_1_id, neighbor_2_id, neighbor_3_id]
    all_ids = [target_id] + neighbor_ids

    frames = {}
    for sid in all_ids:
        if station_frames is not None:
            frames[sid] = station_frames[sid]
        else:
            df = pd.read_sql(
                "SELECT * FROM clean_station_data WHERE station_id = :sid",
                engine,
                params={'sid': sid},
            )
            df = df.drop(columns=['station_id'])
            df['timestamp'] = pd.to_datetime(df['timestamp'])
            df = df.set_index('timestamp').sort_index()
            frames[sid] = df

    placeholders = ','.join(str(sid) for sid in all_ids)
    elevations = pd.read_sql(
        f"SELECT station_id, elevation FROM station_metadata WHERE station_id IN ({placeholders})",
        engine,
    ).set_index('station_id')['elevation']

    df_target = frames[target_id]
    df_neighbors = [frames[nid].add_suffix(f'_n{i + 1}') for i, nid in enumerate(neighbor_ids)]

    combined = df_target.join(df_neighbors, how='inner').dropna()

    y = combined[[c for c in combined.columns if not c.endswith(('_n1', '_n2', '_n3'))]]
    X = combined[[c for c in combined.columns if c.endswith(('_n1', '_n2', '_n3'))]]

    X = X.copy()
    X['elevation_target'] = elevations.get(target_id)
    for i, nid in enumerate(neighbor_ids):
        X[f'elevation_n{i + 1}'] = elevations.get(nid)

    return X, y


def temporal_split_fold(
    X: pd.DataFrame,
    y: pd.DataFrame,
    val_ratio: float = 0.8,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """
    Splits a fold dataset into train and validation sets by time.

    The split point is determined by the val_ratio applied to the sorted
    timestamp index, preserving temporal order. No shuffling is performed.

    :param X: Neighbor feature matrix with timestamp index.
    :param y: Target feature labels with the same timestamp index.
    :param val_ratio: Fraction of data to use for training (default 0.8).
    :returns: (X_train, X_val, y_train, y_val)
    """
    split_idx = int(len(X) * val_ratio)
    split_ts = X.index[split_idx]

    X_train = X[X.index < split_ts]
    X_val = X[X.index >= split_ts]
    y_train = y[y.index < split_ts]
    y_val = y[y.index >= split_ts]

    return X_train, X_val, y_train, y_val
