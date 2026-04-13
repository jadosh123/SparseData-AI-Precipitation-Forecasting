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


def get_k_neighbors(target_id: int, all_stations: dict) -> dict:
    """
    Finds the three best neighbouring stations to use as upstream inputs
    for a target station, using Delaunay-style triangle enclosure.

    The algorithm:
    1. Computes haversine distances from the target to all other stations.
    2. Retains the 10 closest candidates to limit the search space.
    3. Tests all triangles formed by those candidates; keeps ones that
       geometrically enclose the target station.
    4. Selects the enclosing triangle with the smallest area (tightest fit).
    5. If no enclosing triangle exists (boundary station), falls back to the
       3 nearest neighbours by distance.

    :param target_id: Station ID of the target station to find neighbours for.
    :param all_stations: Dict mapping station_id -> (lat, lon).
    :returns: Dict with keys: station_id, is_boundary, triangle_area,
              neighbor_1_id, neighbor_1_distance, neighbor_2_id, ...
    """
    target = all_stations[target_id]

    candidates = [
        (sid, haversine(*target, *coords))
        for sid, coords in all_stations.items()
        if sid != target_id
    ]
    candidates = sorted(candidates, key=lambda x: x[1])[:10]
    candidate_ids = [sid for sid, _ in candidates]

    valid_triangles = []
    for trio in combinations(candidate_ids, 3):
        A = all_stations[trio[0]]
        B = all_stations[trio[1]]
        C = all_stations[trio[2]]
        if point_in_triangle(target, A, B, C):
            area = triangle_area(A, B, C)
            valid_triangles.append((trio, area))

    if valid_triangles:
        best = min(valid_triangles, key=lambda x: x[1])
        neighbors = best[0]
        is_boundary = False
        area = best[1]
    else:
        neighbors = tuple(candidate_ids[:3])
        is_boundary = True
        area = None

    result = {
        'station_id': target_id,
        'is_boundary': is_boundary,
        'triangle_area': area,
    }
    for i, nid in enumerate(neighbors, 1):
        result[f'neighbor_{i}_id'] = nid
        result[f'neighbor_{i}_distance'] = haversine(*target, *all_stations[nid])

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

    print(f"Computing neighbors for {len(all_stations)} stations...")
    records = []
    for station_id in all_stations:
        result = get_k_neighbors(station_id, all_stations)
        result['is_boundary'] = int(result['is_boundary'])
        records.append(result)

    df = pd.DataFrame(records)
    df.to_sql('station_neighbors', engine, if_exists='replace', index=False)
    print(f"Saved {len(df)} rows to station_neighbors.")


def triangle_area(
    A: tuple[float, float],
    B: tuple[float, float],
    C: tuple[float, float],
) -> float:
    """
    Computes the area of triangle ABC using the shoelace formula.

    :param A: First vertex as (x, y).
    :param B: Second vertex as (x, y).
    :param C: Third vertex as (x, y).
    :returns: The area of the triangle (always non-negative).
    """
    return abs(
        (A[0] * (B[1] - C[1]) + B[0] * (C[1] - A[1]) + C[0] * (A[1] - B[1])) / 2
    )
    
if __name__ == "__main__":
    compute_and_store_neighbors()