import numpy as np
from weather_engine.spatial import haversine, point_in_triangle
from itertools import combinations
from weather_engine.database import engine
from weather_engine.utils import get_elevation_from_hgt, get_distance_to_coast
import pandas as pd

LAT_MAX = 32.75
LON_MAX = 35.45
LAT_MIN = 32.45
LON_MIN = 35.05

GRID_STEP_DEG = 0.01  # ~0.935km


def generate_grid_cells() -> list[tuple[float, float]]:
    """
    Generates (lat, lon) grid cell centres for the Jezreel Valley bounding box
    at GRID_STEP_DEG resolution.

    :returns: List of (lat, lon) tuples, one per cell centre.
    """
    lats = np.arange(LAT_MIN, LAT_MAX + GRID_STEP_DEG / 2, GRID_STEP_DEG)
    lons = np.arange(LON_MIN, LON_MAX + GRID_STEP_DEG / 2, GRID_STEP_DEG)
    return [(round(float(lat), 6), round(float(lon), 6)) for lat in lats for lon in lons]


def get_k_neighbors_for_cell(lat: float, lon: float, all_stations: dict) -> dict:
    """
    Finds the three best neighbouring stations for a grid cell centre.

    Prefers a trio that forms a triangle enclosing (lat, lon); falls back to
    the three nearest if no enclosing triangle exists among the top-10 candidates.

    :param lat: Latitude of the grid cell centre.
    :param lon: Longitude of the grid cell centre.
    :param all_stations: Dict mapping station_id -> (lat, lon).
    :returns: Dict with keys: lat, lon, is_boundary, neighbor_1_id, neighbor_1_distance, ...
    """
    all_candidates = sorted(
        [
            (sid, haversine(lat, lon, *coords))
            for sid, coords in all_stations.items()
        ],
        key=lambda x: x[1],
    )[:10]
   
    dist_map = dict(all_candidates)
    candidate_ids = [sid for sid, _ in all_candidates]
    
    interpolation = []
    for trio in combinations(candidate_ids, 3):
        if point_in_triangle((lat, lon), *[all_stations[sid] for sid in trio]):
            interpolation.append((trio, sum(dist_map[sid] for sid in trio)))

    if interpolation:
        best_trio, _ = min(interpolation, key=lambda x: x[1])
        neighbors = [(sid, dist_map[sid]) for sid in best_trio]
        is_boundary = False
    else:
        neighbors = all_candidates[:3]
        is_boundary = True

    result = {'lat': lat, 'lon': lon, 'is_boundary': is_boundary}
    for i, (nid, dist) in enumerate(neighbors, 1):
        result[f'neighbor_{i}_id'] = nid
        result[f'neighbor_{i}_distance'] = dist

    return result
    

def main():
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
    
    # Pop nazareth since its insufficient in data and made all interpolation features regress in accuracy
    all_stations.pop(500, None)
    all_stations.pop(16)
    cells = generate_grid_cells()
    records = []
    for cell in cells:
        res = get_k_neighbors_for_cell(*cell, all_stations)
        res['is_boundary'] = int(res['is_boundary'])
        terrain = get_elevation_from_hgt(*cell)
        res['elevation'] = terrain['elevation']
        res['tpi_local'] = terrain['tpi_local']
        res['tpi_regional'] = terrain['tpi_regional']
        res['roughness_local'] = terrain['roughness_local']
        res['roughness_regional'] = terrain['roughness_regional']
        res['dist_to_coast'] = get_distance_to_coast(*cell)
        records.append(res)
        
    df = pd.DataFrame(records)
    df.to_sql('cell_neighbors', engine, if_exists='append', index=False)
    print(f"Saved {len(df)} rows to cell_neighbors.")


if __name__ == "__main__":
    main()