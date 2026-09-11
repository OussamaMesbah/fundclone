import numpy as np
import pytest

from factorlens.estimators import (
    DEFAULT,
    _overlapping_sums,
    forward_selection,
    make_estimator,
    stable_least_squares,
)
from factorlens.replication import ReplicationConfig, constrained_least_squares

CONFIG = ReplicationConfig(window=400)


def test_forward_selection_respects_the_cap_and_finds_the_right_etfs():
    rng = np.random.default_rng(0)
    X = rng.normal(0, 0.01, size=(400, 20))
    y = X[:, [3, 7]] @ np.array([0.6, 0.4]) + rng.normal(0, 0.0005, 400)
    w = forward_selection(y, X, np.zeros(20), ReplicationConfig(max_etfs=2))
    assert set(np.flatnonzero(w > 1e-6)) == {3, 7}
    assert w[[3, 7]] == pytest.approx([0.6, 0.4], abs=0.02)
    assert w.min() >= 0 and w.sum() <= 1 + 1e-9


def test_forward_selection_stops_when_more_etfs_do_not_help():
    rng = np.random.default_rng(1)
    X = rng.normal(0, 0.01, size=(400, 20))
    w = forward_selection(X[:, 5] * 0.9, X, np.zeros(20), ReplicationConfig(max_etfs=10))
    assert np.flatnonzero(w > 1e-6).tolist() == [5]


def test_forward_selection_prefers_the_etf_already_held():
    x = np.random.default_rng(2).normal(0, 0.01, 400)
    X = np.column_stack([x, x])  # two interchangeable ETFs
    w = forward_selection(x, X, np.array([0.0, 0.5]), ReplicationConfig(window=400, max_etfs=1))
    assert np.flatnonzero(w > 1e-6).tolist() == [1]


def test_stable_least_squares_recovers_a_feasible_portfolio():
    X = np.random.default_rng(3).normal(0, 0.01, size=(400, 6))
    w_true = np.array([0.5, 0.3, 0.2, 0.0, 0.0, 0.0])
    w = stable_least_squares(X @ w_true, X, np.zeros(6), CONFIG)
    assert w == pytest.approx(w_true, abs=1e-4)


def test_stable_least_squares_drops_positions_below_the_minimum_weight():
    rng = np.random.default_rng(4)
    X = rng.normal(0, 0.01, size=(400, 8))
    w_true = np.array([0.5, 0.3, 0.15, 0.01, 0.01, 0.01, 0.0, 0.0])
    y = X @ w_true + rng.normal(0, 0.0005, 400)
    w = stable_least_squares(y, X, np.zeros(8), CONFIG)
    assert (w[w > 0] >= CONFIG.min_weight).all()
    assert w[:3] == pytest.approx([0.5, 0.3, 0.15], abs=0.04)
    kept = stable_least_squares(y, X, np.zeros(8), ReplicationConfig(window=400, min_weight=0))
    assert (kept[3:6] > 0).sum() >= 2  # without trimming the small positions stay


def test_stable_least_squares_keeps_last_months_split_between_twin_etfs():
    rng = np.random.default_rng(5)
    x = rng.normal(0, 0.01, 400)
    X = np.column_stack([x, x + rng.normal(0, 1e-5, 400)])  # the data cannot tell them apart
    left = stable_least_squares(x, X, np.array([0.9, 0.1]), CONFIG)
    right = stable_least_squares(x, X, np.array([0.1, 0.9]), CONFIG)
    assert left[0] > left[1] and right[1] > right[0]
    assert left.sum() == pytest.approx(1.0, abs=0.01)


def test_overlapping_sums():
    values = np.arange(1.0, 6.0)
    assert _overlapping_sums(values, 3).tolist() == [6.0, 9.0, 12.0]
    both = _overlapping_sums(np.column_stack([values, 2 * values]), 2)
    assert both.tolist() == [[3.0, 6.0], [5.0, 10.0], [7.0, 14.0], [9.0, 18.0]]


def test_forward_selection_leaves_out_positions_below_the_minimum():
    rng = np.random.default_rng(6)
    X = rng.normal(0, 0.01, size=(400, 10))
    y = X[:, :3] @ np.array([0.6, 0.39, 0.01]) + rng.normal(0, 0.0002, 400)
    w = forward_selection(y, X, np.zeros(10), ReplicationConfig(window=400, max_etfs=3))
    assert not ((w > 0) & (w < 0.02)).any()
    assert w[:2] == pytest.approx([0.6, 0.39], abs=0.03)


def test_stable_least_squares_holds_cash_when_no_position_reaches_the_minimum():
    rng = np.random.default_rng(7)
    X = rng.normal(0, 0.01, size=(400, 5))
    y = X @ np.full(5, 0.01) + rng.normal(0, 0.0001, 400)
    assert stable_least_squares(y, X, np.zeros(5), CONFIG).sum() == 0


def test_make_estimator_uses_selection_only_when_capped():
    assert make_estimator(ReplicationConfig()) is DEFAULT
    assert make_estimator(ReplicationConfig(max_etfs=3)) is forward_selection
    levered = ReplicationConfig(long_only=False, max_gross=2.0)
    assert make_estimator(levered) is constrained_least_squares
