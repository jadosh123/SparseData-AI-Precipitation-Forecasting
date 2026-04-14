from weather_engine.database import engine
import pandas as pd

FEATURES = ['rain', 'ws', 'stdwd', 'td', 'rh', 'tdmax', 'tdmin', 'u_vec', 'v_vec']


def load_fold(
    target_id: int,
    neighbor_1_id: int,
    neighbor_2_id: int,
    neighbor_3_id: int,
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
        df = pd.read_sql(
            "SELECT timestamp, " + ", ".join(FEATURES) + " FROM clean_station_data WHERE station_id = :sid",
            engine,
            params={'sid': sid},
        )
        df['timestamp'] = pd.to_datetime(df['timestamp'])
        df = df.set_index('timestamp').sort_index()
        frames[sid] = df

    df_target = frames[target_id]
    df_neighbors = [frames[nid].add_suffix(f'_n{i + 1}') for i, nid in enumerate(neighbor_ids)]

    combined = df_target.join(df_neighbors, how='inner').dropna()

    y = combined[[c for c in combined.columns if not c.endswith(('_n1', '_n2', '_n3'))]]
    X = combined[[c for c in combined.columns if c.endswith(('_n1', '_n2', '_n3'))]]

    return X, y
