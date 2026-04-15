import pytest
from weather_engine.spatial import haversine, get_k_neighbors, point_in_triangle, triangle_area


# ---------------------------------------------------------------------------
# haversine
# ---------------------------------------------------------------------------

class TestHaversine:
    def test_same_point_is_zero(self):
        assert haversine(32.0, 34.0, 32.0, 34.0) == pytest.approx(0.0)

    def test_known_distance(self):
        # Tel Aviv (32.0853, 34.7818) to Jerusalem (31.7683, 35.2137) ~ 54 km
        dist = haversine(32.0853, 34.7818, 31.7683, 35.2137)
        assert 50 < dist < 60


# ---------------------------------------------------------------------------
# point_in_triangle
# ---------------------------------------------------------------------------

class TestPointInTriangle:
    def test_point_inside_triangle(self):
        A = (0.0, 0.0)
        B = (4.0, 0.0)
        C = (2.0, 4.0)
        P = (2.0, 1.5)  # clearly inside
        assert point_in_triangle(P, A, B, C) is True

    def test_point_outside_triangle(self):
        A = (0.0, 0.0)
        B = (4.0, 0.0)
        C = (2.0, 4.0)
        P = (5.0, 5.0)  # clearly outside
        assert point_in_triangle(P, A, B, C) is False

    # Method treats 0 cross product as inside
    def test_point_on_edge_is_inside(self):
        A = (0.0, 0.0)
        B = (4.0, 0.0)
        C = (2.0, 4.0)
        P = (2.0, 0.0)  # midpoint of edge AB
        assert point_in_triangle(P, A, B, C) is True


# ---------------------------------------------------------------------------
# triangle_area
# ---------------------------------------------------------------------------

class TestTriangleArea:
    def test_known_right_triangle(self):
        # Right triangle with base=4, height=3 -> area=6
        A = (0.0, 0.0)
        B = (4.0, 0.0)
        C = (0.0, 3.0)
        assert triangle_area(A, B, C) == pytest.approx(6.0)


# ---------------------------------------------------------------------------
# get_k_neighbors
# ---------------------------------------------------------------------------

class TestGetKNeighbors:
    def _make_enclosed_stations(self):
        """
        Target station at center, surrounded by stations forming a clear triangle.
        Station 0 is the target, stations 1-6 surround it.
        """
        return {
            0: (32.0, 35.0),   # target — inside the surrounding stations
            1: (31.0, 34.0),
            2: (31.0, 36.0),
            3: (33.0, 35.0),
            4: (31.5, 34.5),
            5: (31.5, 35.5),
            6: (32.5, 35.0),
        }

    def _make_boundary_stations(self):
        """
        Target station at a corner — no triangle will enclose it,
        forcing the fallback to 3 nearest neighbours.
        """
        return {
            0: (28.0, 30.0),   # target — far corner, outside any formed triangle
            1: (31.0, 34.0),
            2: (32.0, 35.0),
            3: (33.0, 36.0),
            4: (34.0, 37.0),
            5: (35.0, 38.0),
            6: (36.0, 39.0),
        }

    def test_enclosed_triangle_actually_contains_target(self):
        stations = self._make_enclosed_stations()
        result = get_k_neighbors(0, stations, hold_out_station_id=999)
        target = stations[0]
        A = stations[result['neighbor_1_id']]
        B = stations[result['neighbor_2_id']]
        C = stations[result['neighbor_3_id']]
        assert point_in_triangle(target, A, B, C) is True

    def test_enclosed_station_is_not_boundary(self):
        stations = self._make_enclosed_stations()
        result = get_k_neighbors(0, stations, hold_out_station_id=999)
        assert result['is_boundary'] is False
        assert result['triangle_area'] is not None
        assert result['triangle_area'] > 0

    def test_enclosed_station_returns_three_neighbors(self):
        stations = self._make_enclosed_stations()
        result = get_k_neighbors(0, stations, hold_out_station_id=999)
        assert 'neighbor_1_id' in result
        assert 'neighbor_2_id' in result
        assert 'neighbor_3_id' in result

    def test_boundary_station_uses_fallback(self):
        stations = self._make_boundary_stations()
        result = get_k_neighbors(0, stations, hold_out_station_id=999)
        assert result['is_boundary'] is True
        assert result['triangle_area'] is None

    def test_boundary_station_returns_three_nearest(self):
        stations = self._make_boundary_stations()
        result = get_k_neighbors(0, stations, hold_out_station_id=999)
        # The 3 nearest to (28, 30) should be the three stations with smallest coords
        assert result['neighbor_1_id'] == 1
        assert result['neighbor_2_id'] == 2
        assert result['neighbor_3_id'] == 3

    def test_neighbor_distances_are_positive(self):
        stations = self._make_enclosed_stations()
        result = get_k_neighbors(0, stations, hold_out_station_id=999)
        for i in range(1, 4):
            assert result[f'neighbor_{i}_distance'] > 0

    def test_target_not_its_own_neighbor(self):
        stations = self._make_enclosed_stations()
        result = get_k_neighbors(0, stations, hold_out_station_id=999)
        neighbor_ids = {result[f'neighbor_{i}_id'] for i in range(1, 4)}
        assert 0 not in neighbor_ids
