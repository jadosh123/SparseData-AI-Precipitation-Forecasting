
from itertools import combinations
from math import radians, sin, cos, sqrt, atan2
import pandas as pd
from weather_engine.database import engine

def haversine(
    lat1: float, lon1: float,
    lat2: float, lon2: float,
) -> float:
    """
    Computes the great-circle distance between two points on Earth.

    :param lat1: Latitude of point 1 in decimal degrees.
    :param lon1: Longitude of point 1 in decimal degrees.
    :param lat2: Latitude of point 2 in decimal degrees.
    :param lon2: Longitude of point 2 in decimal degrees.
    :returns: Distance in kilometres.
    """
    R = 6371
    dlat = radians(lat2 - lat1)
    dlon = radians(lon2 - lon1)
    a = sin(dlat / 2) ** 2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlon / 2) ** 2
    return R * 2 * atan2(sqrt(a), sqrt(1 - a))


def get_k_neighbors(target_id: int, all_stations: dict, hold_out_station_id: int) -> dict:
    """
    Finds the three nearest neighbouring stations to a target station
    by haversine distance.

    :param target_id: Station ID of the target station to find neighbours for.
    :param all_stations: Dict mapping station_id -> (lat, lon).
    :param hold_out_station_id: Station ID to exclude from candidates.
    :returns: Dict with keys: station_id, neighbor_1_id, neighbor_1_distance, ...
    """
    target = all_stations[target_id]

    all_candidates = sorted(
        [
            (sid, haversine(*target, *coords))
            for sid, coords in all_stations.items()
            if sid != target_id and sid != hold_out_station_id
        ],
        key=lambda x: x[1],
    )[:10]

    dist_map = dict(all_candidates)
    candidate_ids = [sid for sid, _ in all_candidates]

    interpolation = []
    for trio in combinations(candidate_ids, 3):
        if point_in_triangle(target, *[all_stations[sid] for sid in trio]):
            interpolation.append((trio, sum(dist_map[sid] for sid in trio)))

    if interpolation:
        best_trio, _ = min(interpolation, key=lambda x: x[1])
        neighbors = [(sid, dist_map[sid]) for sid in best_trio]
        is_boundary = False
    else:
        neighbors = all_candidates[:3]
        is_boundary = True

    result = {'station_id': target_id, 'is_boundary': is_boundary}
    for i, (nid, dist) in enumerate(neighbors, 1):
        result[f'neighbor_{i}_id'] = nid
        result[f'neighbor_{i}_distance'] = dist

    return result

def point_in_triangle(
    P: tuple[float, float],
    A: tuple[float, float],
    B: tuple[float, float],
    C: tuple[float, float],
) -> bool:
    """
    Tests whether point P lies inside or on the boundary of triangle ABC.

    Uses the sign-of-cross-product barycentric method: computes the signed
    area of the sub-triangles formed by P with each edge. If all signs agree
    (all positive or all negative), P is inside the triangle. Mixed signs
    mean P is outside.

    Points on an edge are considered inside (returns True).

    :param P: The query point as (x, y) — e.g. (longitude, latitude).
    :param A: First vertex of the triangle.
    :param B: Second vertex of the triangle.
    :param C: Third vertex of the triangle.
    :returns: True if P is inside or on the boundary of triangle ABC.
    """
    def sign(p1, p2, p3):
        return (p1[0] - p3[0]) * (p2[1] - p3[1]) - (p2[0] - p3[0]) * (p1[1] - p3[1])

    d1 = sign(P, A, B)
    d2 = sign(P, B, C)
    d3 = sign(P, C, A)

    has_neg = (d1 < 0) or (d2 < 0) or (d3 < 0)
    has_pos = (d1 > 0) or (d2 > 0) or (d3 > 0)

    return not (has_neg and has_pos)

def compute_and_store_neighbors() -> None:
    """
    Computes the 3 best spatial neighbours for every station that has clean data,
    then writes the results to the station_neighbors table.

    Only stations present in both clean_station_data and station_metadata are
    included — this ensures we never use a station whose data was dropped by
    the quality filter in clean_data.py.
    """
    query = """
        SELECT sm.station_id, sm.latitude, sm.longitude
        FROM station_metadata sm
        INNER JOIN (
            SELECT DISTINCT station_id FROM clean_station_data
        ) csd ON sm.station_id = csd.station_id
    """
    coords_df = pd.read_sql(query, engine)
    all_stations = {
        int(sid): (float(lat), float(lon))
        for sid, lat, lon in zip(coords_df['station_id'], coords_df['latitude'], coords_df['longitude'])
    }
    
    ### FOR TRAINING/TESTING IN DEVELOPMENT PHASE (NAZARETH HAS NO DATA OLDER THAN 2024)
    NAZARETH_ID = 500
    all_stations.pop(NAZARETH_ID)

    print(f"Computing neighbors for {len(all_stations)} stations...")
    records = []
    for station_id in all_stations:
        result = get_k_neighbors(station_id, all_stations, 16)
        result['is_boundary'] = int(result['is_boundary'])
        records.append(result)

    df = pd.DataFrame(records)
    df.to_sql('station_neighbors', engine, if_exists='replace', index=False)
    print(f"Saved {len(df)} rows to station_neighbors.")

if __name__ == "__main__":
    compute_and_store_neighbors()