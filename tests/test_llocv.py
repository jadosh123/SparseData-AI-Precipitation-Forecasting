import pandas as pd
import pytest
from weather_engine.llocv import load_fold, temporal_split_fold

# Station IDs handpicked for distinct missing segments:
#   8   → gap 2020-06-28 : 2020-09-10  (stdwd/ws/u_vec/v_vec outage ~74 days)
#   28  → gap 2020-03-19 : 2020-05-24  (stdwd/u_vec/v_vec outage ~66 days)
#   43  → gap 2019-12-31 : 2020-06-29  (ws/stdwd/u_vec/v_vec outage ~180 days)
#   121 → gap 2023-01-04 : 2023-01-05
TARGET_ID = 8
NEIGHBOR_IDS = (28, 43, 121)

GAP_RANGES = [
    ('2020-03-19 01:00', '2020-05-24 09:00'),   # station 28 worst gap
    ('2019-12-31 22:00', '2020-06-29 12:00'),   # station 43 worst gap
    ('2023-01-04 18:00', '2023-01-05 12:00'),   # station 121 worst gap
]

NEIGHBOR_SUFFIXES = ('_n1', '_n2', '_n3')


@pytest.fixture(scope='module')
def fold():
    X, y = load_fold(TARGET_ID, *NEIGHBOR_IDS)
    return X, y


class TestLoadFoldTargetIsolation:
    def test_X_contains_only_neighbor_and_elevation_columns(self, fold):
        X, _ = fold
        allowed_extra = {'elevation_target'}
        bare = [c for c in X.columns if not c.endswith(NEIGHBOR_SUFFIXES) and c not in allowed_extra]
        assert bare == [], f"X contains unexpected columns: {bare}"

    def test_X_has_elevation_columns(self, fold):
        X, _ = fold
        expected = {'elevation_target', 'elevation_n1', 'elevation_n2', 'elevation_n3'}
        assert expected.issubset(set(X.columns)), f"Missing elevation columns: {expected - set(X.columns)}"

    def test_y_contains_only_target_feature_columns(self, fold):
        _, y = fold
        assert not any(c.endswith(NEIGHBOR_SUFFIXES) or 'elevation' in c for c in y.columns)

    def test_X_and_y_share_same_index(self, fold):
        X, y = fold
        assert X.index.equals(y.index)

    def test_no_nulls_in_X(self, fold):
        X, _ = fold
        assert not X.isnull().any().any()

    def test_no_nulls_in_y(self, fold):
        _, y = fold
        assert not y.isnull().any().any()


class TestTemporalSplitFold:
    VAL_RATIO = 0.8

    @pytest.fixture(scope='class')
    def split(self, fold):
        X, y = fold
        return temporal_split_fold(X, y, val_ratio=self.VAL_RATIO)

    def test_train_val_lengths_match_ratio(self, split):
        X_train, X_val, _, _ = split
        total = len(X_train) + len(X_val)
        assert len(X_train) == int(total * self.VAL_RATIO)
        assert len(X_val) == total - int(total * self.VAL_RATIO)

    def test_X_and_y_splits_are_same_length(self, split):
        X_train, X_val, y_train, y_val = split
        assert len(X_train) == len(y_train)
        assert len(X_val) == len(y_val)

    def test_train_ends_before_val_starts(self, split):
        X_train, X_val, _, _ = split
        assert X_train.index.max() < X_val.index.min()

    def test_no_timestamp_overlap(self, split):
        X_train, X_val, _, _ = split
        overlap = X_train.index.intersection(X_val.index)
        assert len(overlap) == 0


class TestLoadFoldGapsExcluded:
    @pytest.mark.parametrize("gap_start,gap_end", GAP_RANGES)
    def test_gap_timestamps_absent_from_index(self, fold, gap_start, gap_end):
        X, y = fold
        mask = (X.index >= gap_start) & (X.index <= gap_end)
        timestamps_in_gap = X.index[mask]
        assert len(timestamps_in_gap) == 0, (
            f"Found {len(timestamps_in_gap)} timestamps between {gap_start} and "
            f"{gap_end} that should have been dropped:\n{timestamps_in_gap[:5]}"
        )
