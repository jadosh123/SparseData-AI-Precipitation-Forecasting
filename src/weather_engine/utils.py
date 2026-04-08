from pathlib import Path
import math
import pandas as pd
import rasterio

def get_project_root() -> Path:
    """
    Finds and returns the project root by traversing upwards from the current 
    file's directory until a .toml file (such as pyproject.toml) is found.
    
    Returns:
        Path: The absolute path to the project's root directory.
        
    Raises:
        FileNotFoundError: If the root of the file system is reached without finding a .toml file.
    """
    current_path = Path(__file__).resolve().parent
    
    while current_path != current_path.parent:
        # Check if there are any .toml files in the current directory
        if list(current_path.glob("*.toml")):
            return current_path
            
        # Move up one level
        current_path = current_path.parent
        
    raise FileNotFoundError("Could not find the project root (no .toml file found in any parent directories).")

def get_elevation_from_hgt(lat, lon):
    """Uses rasterio to pinpoint a latitude/longitude and extract its exact elevation from the .hgt tile."""

    if pd.isna(lat) or pd.isna(lon):
        return None
        
    hgt_dir = get_project_root() / 'data' / 'elevation_data'
    lat_prefix = 'N' if lat >= 0 else 'S'
    lon_prefix = 'E' if lon >= 0 else 'W'
    
    lat_int = math.floor(abs(lat))
    lon_int = math.floor(abs(lon))
    
    tile_name = f"{lat_prefix}{lat_int:02d}{lon_prefix}{lon_int:03d}.hgt"
    tile_path = hgt_dir / tile_name
    
    if not tile_path.exists():
        return None
        
    try:
        with rasterio.open(tile_path) as src:
            for val in src.sample([(lon, lat)]):
                elev = val[0]
                if int(elev) == -32768:  # SRTM NoData
                    return None
                return float(elev)
    except Exception as e:
        print(f"Error reading {tile_name}: {e}")
        return None

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