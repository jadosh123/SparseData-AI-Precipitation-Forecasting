import pytest
import pandas as pd
import numpy as np
from weather_engine.database import engine
from weather_engine.cell_generation import get_k_neighbors_for_cell
from weather_engine.cell_interpolation import load_cell_features
from weather_engine.cell_forecasting import create_local_lags, add_upstream_features, make_inference_features


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def cell_interpolated():
    return pd.read_sql("SELECT * FROM cell_interpolated", engine)


@pytest.fixture(scope="module")
def cell_forecasts():
    return pd.read_sql("SELECT * FROM cell_forecasts", engine)


@pytest.fixture(scope="module")
def cell_neighbors():
    return pd.read_sql("SELECT * FROM cell_neighbors", engine)


# ---------------------------------------------------------------------------
# cell_generation
# ---------------------------------------------------------------------------

class TestCellGeneration:
    def test_returns_three_neighbors(self):
        stations = {
            1: (32.5, 35.1),
            2: (32.6, 35.2),
            3: (32.7, 35.3),
            4: (32.5, 35.4),
        }
        result = get_k_neighbors_for_cell(32.6, 35.2, stations)
        assert 'neighbor_1_id' in result
        assert 'neighbor_2_id' in result
        assert 'neighbor_3_id' in result

    def test_distances_are_positive(self):
        stations = {
            1: (32.5, 35.1),
            2: (32.6, 35.3),
            3: (32.7, 35.2),
            4: (32.4, 35.4),
        }
        result = get_k_neighbors_for_cell(32.6, 35.2, stations)
        assert result['neighbor_1_distance'] > 0
        assert result['neighbor_2_distance'] > 0
        assert result['neighbor_3_distance'] > 0

    def test_neighbor_ids_are_in_station_pool(self):
        stations = {10: (32.5, 35.1), 20: (32.7, 35.2), 30: (32.6, 35.4), 40: (32.4, 35.3)}
        result = get_k_neighbors_for_cell(32.6, 35.2, stations)
        for key in ['neighbor_1_id', 'neighbor_2_id', 'neighbor_3_id']:
            assert result[key] in stations

    def test_afula_excluded_from_cell_neighbors(self, cell_neighbors):
        afula_id = 16
        for col in ['neighbor_1_id', 'neighbor_2_id', 'neighbor_3_id']:
            leakers = cell_neighbors[cell_neighbors[col] == afula_id]
            assert leakers.empty, (
                f"Afula (id={afula_id}) found as {col} for cells: {leakers['cell_id'].tolist()}"
            )


# ---------------------------------------------------------------------------
# cell_interpolation
# ---------------------------------------------------------------------------

class TestLoadCellFeatures:
    # Use real station IDs so the station_metadata DB lookup succeeds
    NEIGHBOR_IDS = (2, 6, 8)

    @pytest.fixture(scope="class")
    def synthetic_frames(self):
        idx = pd.date_range("2020-01-01", periods=100, freq="h")
        def make_frame():
            return pd.DataFrame({
                'rain': np.random.uniform(0, 5, 100),
                'ws': np.random.uniform(0, 10, 100),
                'td': np.random.uniform(5, 25, 100),
                'rh': np.random.uniform(40, 90, 100),
                'tdmax': np.random.uniform(15, 30, 100),
                'tdmin': np.random.uniform(5, 15, 100),
                'u_vec': np.random.uniform(-5, 5, 100),
                'v_vec': np.random.uniform(-5, 5, 100),
            }, index=idx)
        return {sid: make_frame() for sid in self.NEIGHBOR_IDS}

    def test_returns_dataframe(self, synthetic_frames):
        X = load_cell_features(100.0, 10.0, *self.NEIGHBOR_IDS, 5.0, 8.0, 12.0, station_frames=synthetic_frames)
        assert isinstance(X, pd.DataFrame)

    def test_static_features_present(self, synthetic_frames):
        X = load_cell_features(100.0, 10.0, *self.NEIGHBOR_IDS, 5.0, 8.0, 12.0, station_frames=synthetic_frames)
        assert 'elevation_target' in X.columns
        assert 'dist_to_coast_target' in X.columns
        assert 'dist_n1' in X.columns
        assert 'dist_n2' in X.columns
        assert 'dist_n3' in X.columns

    def test_neighbor_suffixes_present(self, synthetic_frames):
        X = load_cell_features(100.0, 10.0, *self.NEIGHBOR_IDS, 5.0, 8.0, 12.0, station_frames=synthetic_frames)
        assert any(c.endswith('_n1') for c in X.columns)
        assert any(c.endswith('_n2') for c in X.columns)
        assert any(c.endswith('_n3') for c in X.columns)

    def test_distances_match_input(self, synthetic_frames):
        X = load_cell_features(100.0, 10.0, *self.NEIGHBOR_IDS, 5.5, 8.5, 12.5, station_frames=synthetic_frames)
        assert (X['dist_n1'] == 5.5).all()
        assert (X['dist_n2'] == 8.5).all()
        assert (X['dist_n3'] == 12.5).all()


# ---------------------------------------------------------------------------
# cell_forecasting
# ---------------------------------------------------------------------------

class TestCellForecasting:
    @pytest.fixture
    def synthetic_target(self):
        idx = pd.date_range("2020-01-01", periods=200, freq="h")
        return pd.DataFrame({
            'rain': np.random.uniform(0, 5, 200),
            'ws': np.random.uniform(0, 10, 200),
            'td': np.random.uniform(5, 25, 200),
            'rh': np.random.uniform(40, 90, 200),
            'tdmax': np.random.uniform(15, 30, 200),
            'tdmin': np.random.uniform(5, 15, 200),
            'u_vec': np.random.uniform(-5, 5, 200),
            'v_vec': np.random.uniform(-5, 5, 200),
        }, index=idx)

    @pytest.fixture
    def synthetic_upstream(self):
        idx = pd.date_range("2020-01-01", periods=200, freq="h")
        def make():
            return pd.DataFrame({
                'rain': np.random.uniform(0, 5, 200),
                'u_vec': np.random.uniform(-5, 5, 200),
                'v_vec': np.random.uniform(-5, 5, 200),
                'rh': np.random.uniform(40, 90, 200),
            }, index=idx)
        return {"tel_aviv": make(), "haifa": make()}

    def test_create_local_lags_adds_columns(self, synthetic_target):
        out = create_local_lags(synthetic_target)
        assert 'rain_t-1h' in out.columns
        assert 'rain_t-24h' in out.columns
        assert 'rh_t-6h' in out.columns

    def test_make_inference_features_drops_warmup(self, synthetic_target, synthetic_upstream):
        X = make_inference_features(synthetic_target, synthetic_upstream, max_lag_hours=24)
        assert len(X) <= len(synthetic_target) - 24

    def test_make_inference_features_no_nulls(self, synthetic_target, synthetic_upstream):
        X = make_inference_features(synthetic_target, synthetic_upstream)
        assert not X.isnull().any().any()


# ---------------------------------------------------------------------------
# cell_interpolated DB sanity checks
# ---------------------------------------------------------------------------

class TestCellInterpolatedIntegrity:
    def test_no_negative_rain(self, cell_interpolated):
        bad = cell_interpolated['rain'].dropna()
        bad = bad[bad < 0]
        assert bad.empty, f"Found {len(bad)} negative rain values in cell_interpolated."

    def test_temperature_bounds(self, cell_interpolated):
        for col in ['td', 'tdmax', 'tdmin']:
            vals = cell_interpolated[col].dropna()
            assert (vals > -10).all(), f"Impossibly low values in {col}."
            assert (vals < 50).all(), f"Impossibly high values in {col}."

    def test_rh_bounds(self, cell_interpolated):
        rh = cell_interpolated['rh'].dropna()
        assert (rh >= 0).all(), "Negative RH values found."
        assert (rh <= 100).all(), "RH values above 100% found."

    def test_no_duplicate_cell_timestamp(self, cell_interpolated):
        dupes = cell_interpolated.duplicated(subset=['cell_id', 'timestamp'])
        assert not dupes.any(), f"Found {dupes.sum()} duplicate (cell_id, timestamp) pairs."

    def test_all_cells_present(self, cell_interpolated, cell_neighbors):
        interpolated_ids = set(cell_interpolated['cell_id'].unique())
        neighbor_ids = set(cell_neighbors['cell_id'].unique())
        assert interpolated_ids == neighbor_ids, (
            f"Cells in cell_neighbors but missing from cell_interpolated: "
            f"{neighbor_ids - interpolated_ids}"
        )


# ---------------------------------------------------------------------------
# cell_forecasts DB sanity checks
# ---------------------------------------------------------------------------

class TestCellForecastsIntegrity:
    def test_no_negative_precipitation(self, cell_forecasts):
        for col in ['precipitation_t1', 'precipitation_t3', 'precipitation_t6', 'precipitation_t12']:
            bad = cell_forecasts[col].dropna()
            bad = bad[bad < 0]
            assert bad.empty, f"Found {len(bad)} negative values in {col}."

    def test_no_duplicate_cell_timestamp(self, cell_forecasts):
        dupes = cell_forecasts.duplicated(subset=['cell_id', 'timestamp'])
        assert not dupes.any(), f"Found {dupes.sum()} duplicate (cell_id, timestamp) pairs."

    def test_all_cells_present(self, cell_forecasts, cell_neighbors):
        forecast_ids = set(cell_forecasts['cell_id'].unique())
        neighbor_ids = set(cell_neighbors['cell_id'].unique())
        assert forecast_ids == neighbor_ids, (
            f"Cells in cell_neighbors but missing from cell_forecasts: "
            f"{neighbor_ids - forecast_ids}"
        )

    def test_forecast_row_count_less_than_interpolated(self, cell_forecasts, cell_interpolated):
        assert len(cell_forecasts) < len(cell_interpolated), (
            "Forecast table should have fewer rows than interpolated due to lag warmup."
        )

    def test_longer_horizon_not_always_higher(self, cell_forecasts):
        # Sanity: t+12 should not always be >= t+1 (would indicate a degenerate model)
        always_higher = (cell_forecasts['precipitation_t12'] >= cell_forecasts['precipitation_t1']).all()
        assert not always_higher, "precipitation_t12 is always >= t1 which suggests a degenerate model."
