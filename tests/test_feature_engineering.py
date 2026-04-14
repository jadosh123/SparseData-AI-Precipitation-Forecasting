import pytest
import pandas as pd
import numpy as np
from weather_engine.single_point_features import (
    single_station_load,
    sort_by_ts,
    create_local_lags,
    add_upstream_features,
    get_constraints,
    temporal_split,
    create_production_backbone,
    prepare_dataset,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def db_station_df():
    """Loads a real station from the DB once for the whole session."""
    try:
        return single_station_load(16)
    except Exception as e:
        pytest.fail(f"Database connection failed: {e}")


def _make_df(n=48, with_nans=False, seed=0):
    """Helper: builds a minimal station-like DataFrame with a DatetimeIndex."""
    rng = np.random.default_rng(seed)
    idx = pd.date_range("2023-01-01", periods=n, freq="h")
    df = pd.DataFrame({
        "rain":             rng.uniform(0, 5, n),
        "u_vec":            rng.uniform(-5, 5, n),
        "v_vec":            rng.uniform(-5, 5, n),
        "td":               rng.uniform(10, 30, n),
        "rh":               rng.uniform(30, 100, n),
        "rain_intensity_max": rng.uniform(0, 10, n),
        "ws":               rng.uniform(0, 15, n),
    }, index=idx)
    df.index.name = "timestamp"
    if with_nans:
        for col in ["rain", "u_vec", "rh"]:
            df.loc[df.sample(frac=0.2, random_state=seed).index, col] = np.nan
    return df


# ---------------------------------------------------------------------------
# single_station_load
# ---------------------------------------------------------------------------

class TestSingleStationLoad:
    def test_returns_dataframe(self, db_station_df):
        assert isinstance(db_station_df, pd.DataFrame)

    def test_not_empty(self, db_station_df):
        assert not db_station_df.empty

    def test_has_expected_columns(self, db_station_df):
        for col in ["station_id", "timestamp", "rain", "td"]:
            assert col in db_station_df.columns, f"Missing column: {col}"

    def test_single_station_only(self, db_station_df):
        assert db_station_df["station_id"].nunique() == 1


# ---------------------------------------------------------------------------
# sort_by_ts
# ---------------------------------------------------------------------------

class TestSortByTs:
    def test_index_is_datetime(self, db_station_df):
        result = sort_by_ts(db_station_df)
        assert isinstance(result.index, pd.DatetimeIndex)

    def test_index_is_sorted(self, db_station_df):
        shuffled = db_station_df.sample(frac=1, random_state=42)
        result = sort_by_ts(shuffled)
        assert result.index.is_monotonic_increasing

    def test_with_mixed_timestamp_formats(self):
        df = pd.DataFrame({
            "timestamp": ["2023-03-01 10:00", "2023-01-01 00:00", "2023-06-15 12:30"],
            "rain": [1.0, 0.0, 2.0],
        })
        result = sort_by_ts(df)
        assert result.index.is_monotonic_increasing

    def test_with_invalid_timestamps_coerced(self):
        df = pd.DataFrame({
            "timestamp": ["2023-01-01", "not_a_date", "2023-01-03"],
            "rain": [1.0, 0.5, 2.0],
        })
        result = sort_by_ts(df)
        assert isinstance(result.index, pd.DatetimeIndex)
        assert result.index.isna().sum() == 1


# ---------------------------------------------------------------------------
# create_local_lags
# ---------------------------------------------------------------------------

class TestCreateLocalLags:
    def test_target_column_created(self):
        df = _make_df()
        result = create_local_lags(df, target_lag=3)
        assert "target_rain_t+3" in result.columns

    def test_lag_columns_created(self):
        df = _make_df()
        result = create_local_lags(df, lag_hours=[1, 6])
        assert "rain_t-1h" in result.columns
        assert "rain_t-6h" in result.columns

    def test_lag_shift_values_correct(self):
        df = _make_df()
        result = create_local_lags(df, lag_hours=[1], target_lag=1)
        # row at index 1 should have rain_t-1h == row 0's rain
        assert result["rain_t-1h"].iloc[1] == pytest.approx(df["rain"].iloc[0])

    def test_target_shift_values_correct(self):
        df = _make_df()
        result = create_local_lags(df, target_lag=2)
        assert result["target_rain_t+2"].iloc[0] == pytest.approx(df["rain"].iloc[2])

    def test_does_not_mutate_input(self):
        df = _make_df()
        cols_before = set(df.columns)
        create_local_lags(df)
        assert set(df.columns) == cols_before

    def test_with_all_nan_rain(self):
        df = _make_df()
        df["rain"] = np.nan
        result = create_local_lags(df, target_lag=1)
        assert result["target_rain_t+1"].isna().all()

    def test_missing_optional_columns_skipped(self):
        df = _make_df()[["rain", "td"]]
        result = create_local_lags(df, lag_hours=[1])
        assert "rain_t-1h" in result.columns
        assert "rh_t-1h" not in result.columns


# ---------------------------------------------------------------------------
# add_upstream_features
# ---------------------------------------------------------------------------

class TestAddUpstreamFeatures:
    def test_upstream_cols_added(self):
        target = _make_df(seed=0)
        upstream = _make_df(seed=1)
        result = add_upstream_features(target, upstream, upstream_name="up")
        assert "rain_up" in result.columns
        assert "u_convergence_up" in result.columns
        assert "moisture_flux_up" in result.columns

    def test_lag_cols_added(self):
        target = _make_df(seed=0)
        upstream = _make_df(seed=1)
        result = add_upstream_features(target, upstream, upstream_name="up", lag_hours=[1, 3])
        assert "rain_up_t-1h" in result.columns
        assert "rain_up_t-3h" in result.columns

    def test_row_count_preserved(self):
        target = _make_df(seed=0)
        upstream = _make_df(seed=1)
        result = add_upstream_features(target, upstream, upstream_name="up")
        assert len(result) == len(target)

    def test_convergence_is_difference(self):
        target = _make_df(seed=0)
        upstream = _make_df(seed=1)
        result = add_upstream_features(target, upstream, upstream_name="up")
        expected = upstream["u_vec"].reindex(target.index) - target["u_vec"]
        pd.testing.assert_series_equal(
            result["u_convergence_up"], expected, check_names=False, check_like=True
        )

    def test_misaligned_index_produces_nans(self):
        target = _make_df(n=24, seed=0)
        upstream = _make_df(n=24, seed=1)
        upstream.index = upstream.index + pd.Timedelta(days=365)
        result = add_upstream_features(target, upstream, upstream_name="up")
        assert result["rain_up"].isna().all()

    def test_with_nan_upstream(self):
        target = _make_df(seed=0)
        upstream = _make_df(with_nans=True, seed=1)
        result = add_upstream_features(target, upstream, upstream_name="up")
        assert isinstance(result, pd.DataFrame)


# ---------------------------------------------------------------------------
# get_constraints
# ---------------------------------------------------------------------------

class TestGetConstraints:
    def test_rain_col_gets_positive_constraint(self):
        df = pd.DataFrame(columns=["rain_t-1h", "td_t-1h", "target_rain_t+1"])
        result = get_constraints(df)
        assert result.get("rain_t-1h") == 1

    def test_td_col_gets_negative_constraint(self):
        df = pd.DataFrame(columns=["rain_t-1h", "td_t-1h", "target_rain_t+1"])
        result = get_constraints(df)
        assert result.get("td_t-1h") == -1

    def test_target_col_excluded(self):
        df = pd.DataFrame(columns=["rain_t-1h", "target_rain_t+1"])
        result = get_constraints(df)
        assert "target_rain_t+1" not in result

    def test_unrelated_col_not_in_constraints(self):
        df = pd.DataFrame(columns=["ws_t-1h", "target_rain_t+1"])
        result = get_constraints(df)
        assert "ws_t-1h" not in result

    def test_empty_df_returns_empty_dict(self):
        df = pd.DataFrame()
        result = get_constraints(df)
        assert result == {}

    def test_convergence_gets_positive_constraint(self):
        df = pd.DataFrame(columns=["u_convergence_haifa", "target_rain_t+1"])
        result = get_constraints(df)
        assert result.get("u_convergence_haifa") == 1


# ---------------------------------------------------------------------------
# temporal_split
# ---------------------------------------------------------------------------

class TestTemporalSplit:
    def _make_split_df(self):
        idx = pd.date_range("2022-01-01", periods=365 * 3, freq="D")
        df = pd.DataFrame({
            "feature_a": np.random.rand(len(idx)),
            "target_rain_t+1": np.random.rand(len(idx)),
        }, index=idx)
        return df

    def test_split_sizes_are_correct(self):
        df = self._make_split_df()
        X_train, X_val, X_test, y_train, y_val, y_test = temporal_split(
            df, "target_rain_t+1", "2024-01-01", "2024-07-01"
        )
        assert len(X_train) + len(X_val) + len(X_test) == len(df)

    def test_no_temporal_leakage(self):
        df = self._make_split_df()
        X_train, X_val, X_test, *_ = temporal_split(
            df, "target_rain_t+1", "2024-01-01", "2024-07-01"
        )
        assert X_train.index.max() < pd.Timestamp("2024-01-01")
        assert X_val.index.min() >= pd.Timestamp("2024-01-01")
        assert X_test.index.min() >= pd.Timestamp("2024-07-01")

    def test_target_col_excluded_from_features(self):
        df = self._make_split_df()
        X_train, *_ = temporal_split(df, "target_rain_t+1", "2024-01-01", "2024-07-01")
        assert "target_rain_t+1" not in X_train.columns

    def test_y_matches_x_index(self):
        df = self._make_split_df()
        X_train, X_val, X_test, y_train, y_val, y_test = temporal_split(
            df, "target_rain_t+1", "2024-01-01", "2024-07-01"
        )
        pd.testing.assert_index_equal(X_train.index, y_train.index)
        pd.testing.assert_index_equal(X_val.index, y_val.index)
        pd.testing.assert_index_equal(X_test.index, y_test.index)

    def test_val_is_bounded_between_train_and_test(self):
        df = self._make_split_df()
        X_train, X_val, X_test, *_ = temporal_split(
            df, "target_rain_t+1", "2024-01-01", "2024-07-01"
        )
        assert X_val.index.max() < pd.Timestamp("2024-07-01")
        assert X_val.index.min() >= pd.Timestamp("2024-01-01")


# ---------------------------------------------------------------------------
# create_production_backbone
# ---------------------------------------------------------------------------

class TestCreateProductionBackbone:
    def test_starts_after_warmup(self):
        result = create_production_backbone("2020-01-01", "2020-02-01", max_lag_hours=24)
        assert result.index[0] == pd.Timestamp("2020-01-02 00:00:00")

    def test_ends_at_end_date(self):
        result = create_production_backbone("2020-01-01", "2020-02-01", max_lag_hours=24)
        assert result.index[-1] == pd.Timestamp("2020-02-01 00:00:00")

    def test_hourly_frequency(self):
        result = create_production_backbone("2020-01-01", "2020-01-05", max_lag_hours=24)
        assert result.index.freq == "h" or (result.index[1] - result.index[0]) == pd.Timedelta(hours=1)

    def test_index_name_is_timestamp(self):
        result = create_production_backbone("2020-01-01", "2020-02-01", max_lag_hours=24)
        assert result.index.name == "timestamp"

    def test_zero_warmup(self):
        result = create_production_backbone("2020-01-01", "2020-01-03", max_lag_hours=0)
        assert result.index[0] == pd.Timestamp("2020-01-01 00:00:00")


# ---------------------------------------------------------------------------
# prepare_dataset
# ---------------------------------------------------------------------------

class TestPrepareDataset:
    def test_target_column_present(self):
        df = _make_df(n=100)
        result = prepare_dataset(df, target_lag=1, max_lag=24)
        assert "target_rain_t+1" in result.columns

    def test_warmup_rows_trimmed(self):
        df = _make_df(n=100)
        result = prepare_dataset(df, target_lag=1, max_lag=24)
        assert len(result) <= len(df) - 24

    def test_no_nan_in_target(self):
        df = _make_df(n=100)
        result = prepare_dataset(df, target_lag=1, max_lag=24)
        assert result["target_rain_t+1"].isna().sum() == 0

    def test_different_lags_produce_different_targets(self):
        df = _make_df(n=100)
        r1 = prepare_dataset(df, target_lag=1)
        r6 = prepare_dataset(df, target_lag=6)
        assert "target_rain_t+1" in r1.columns
        assert "target_rain_t+6" in r6.columns
        assert "target_rain_t+1" not in r6.columns

    def test_with_nan_heavy_data(self):
        df = _make_df(n=100, with_nans=True)
        result = prepare_dataset(df, target_lag=1, max_lag=24)
        assert result["target_rain_t+1"].isna().sum() == 0
