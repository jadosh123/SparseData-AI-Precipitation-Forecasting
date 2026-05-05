import pandas as pd
from weather_engine.database import engine

def load_cell_features(
    cell_elevation: float,
    cell_dist_to_coast: float,
    neighbor_1_id: int,
    neighbor_2_id: int,
    neighbor_3_id: int,
    station_frames: dict,
) -> pd.DataFrame:
    """
    Builds the RFSI feature matrix for a single grid cell.

    Joins neighbor time-series from station_frames on inner timestamps, drops
    rows with any null, then appends static features for the cell and its neighbors.

    :param cell_elevation: Elevation of the grid cell in metres.
    :param cell_dist_to_coast: Signed distance to nearest coastline in km (negative = land side).
    :param neighbor_1_id: Station ID of first neighbor.
    :param neighbor_2_id: Station ID of second neighbor.
    :param neighbor_3_id: Station ID of third neighbor.
    :param station_frames: Dict mapping station_id -> cleaned DataFrame indexed by timestamp.
    :returns: Feature matrix X with neighbor columns suffixed _n1/_n2/_n3 and static features.
    """
    neighbor_ids = [neighbor_1_id, neighbor_2_id, neighbor_3_id]

    placeholders = ','.join(str(sid) for sid in neighbor_ids)
    metadata = pd.read_sql(
        f"SELECT * FROM station_metadata WHERE station_id IN ({placeholders})",
        engine,
    ).set_index('station_id')

    df_neighbors = [station_frames[nid].add_suffix(f'_n{i + 1}') for i, nid in enumerate(neighbor_ids)]
    X = df_neighbors[0].join(df_neighbors[1:], how='inner').dropna()
    
    X = X.copy()
    X['elevation_target'] = cell_elevation
    X['dist_to_coast_target'] = cell_dist_to_coast
    for i, nid in enumerate(neighbor_ids):
        X[f'elevation_n{i+1}'] = metadata.loc[nid, 'elevation']
        X[f'dist_to_coast_n{i+1}'] = metadata.loc[nid, 'dist_to_coast']

    return X
