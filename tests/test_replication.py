import numpy as np
import pandas as pd
import pytest
from scipy.optimize import nnls

from fundclone.estimators import make_estimator
from fundclone.replication import (
    ReplicationConfig,
    ReplicationResult,
    estimate_weights,
    rebalance_dates,
    simulate_clone,
    walk_forward,
)


def market(n=900, seed=1):
    rng = np.random.default_rng(seed)
    index = pd.bdate_range("2015-01-01", periods=n)
    assets = pd.DataFrame(
        rng.normal(0.0004, 0.01, size=(n, 4)), index=index, columns=["A", "B", "C", "D"]
    )
    return assets, pd.Series(0.0001, index=index)


def test_recovers_a_feasible_portfolio_exactly():
    X = np.random.default_rng(0).normal(0, 0.01, size=(500, 4))
    w_true = np.array([0.5, 0.3, 0.0, 0.2])
    assert estimate_weights(X @ w_true, X) == pytest.approx(w_true, abs=1e-5)


def test_matches_nnls_when_the_exposure_cap_is_slack():
    rng = np.random.default_rng(2)
    X = rng.normal(0, 0.01, size=(300, 5))
    y = X @ np.array([0.2, -0.3, 0.4, 0.1, 0.0]) + rng.normal(0, 0.002, 300)
    expected, _ = nnls(X, y)
    assert estimate_weights(y, X, long_only=True, max_gross=10.0) == pytest.approx(
        expected, abs=1e-5
    )


def test_exposure_cap_binds():
    X = np.random.default_rng(3).normal(0, 0.01, size=(300, 3))
    w = estimate_weights(X @ np.array([1.0, 0.8, 0.5]), X, long_only=True, max_gross=1.5)
    assert w.sum() == pytest.approx(1.5, abs=1e-6)
    assert (w >= 0).all()


def test_long_short_weights():
    X = np.random.default_rng(4).normal(0, 0.01, size=(400, 3))
    w_true = np.array([0.8, -0.3, 0.2])
    assert estimate_weights(X @ w_true, X, long_only=False, max_gross=2.0) == pytest.approx(
        w_true, abs=1e-5
    )
    capped = estimate_weights(X @ w_true, X, long_only=False, max_gross=1.0)
    assert np.abs(capped).sum() == pytest.approx(1.0, abs=1e-6)


def test_rebalance_dates():
    index = pd.bdate_range("2024-01-01", "2024-06-28")
    dates = rebalance_dates(index, "M", window=30)
    # 31 January is only the 23rd trading day; 28 June is the last date, with nothing after it
    assert list(dates) == [
        pd.Timestamp(d) for d in ["2024-02-29", "2024-03-29", "2024-04-30", "2024-05-31"]
    ]
    assert list(rebalance_dates(index, "Q", window=30)) == [pd.Timestamp("2024-03-29")]


def test_leverage_pays_financing_and_trading_costs():
    index = pd.bdate_range("2024-01-01", periods=253)
    weights = pd.DataFrame({"A": [2.0]}, index=[index[0]])
    sim = simulate_clone(
        weights,
        pd.DataFrame({"A": 0.0}, index=index),
        pd.Series(0.0001, index=index),
        financing_spread=0.01,
        cost_bps=10,
    )
    # buy 2x NAV for 10 bp of 2, then owe 1 plus that fee at the T-bill rate plus 1% p.a.
    expected = 2 - (1 + 2 * 0.001) * (1 + 0.0001 + 0.01 / 252) ** 252
    assert (1 + sim.returns).prod() == pytest.approx(expected)
    assert sim.turnover.iloc[0] == pytest.approx(2.0)
    assert len(sim.returns) == 252


def test_short_positions_earn_rf_on_proceeds_and_pay_borrow_fee():
    index = pd.bdate_range("2024-01-01", periods=253)
    rf, fee = 0.0001, 0.01 / 252
    sim = simulate_clone(
        pd.DataFrame({"A": [-1.0]}, index=[index[0]]),
        pd.DataFrame({"A": 0.0}, index=index),
        pd.Series(rf, index=index),
        financing_spread=0.01,
    )
    growth = (1 + rf) ** 252
    cash = 2 * growth - fee * (growth - 1) / rf
    assert (1 + sim.returns).prod() == pytest.approx(cash - 1)


def test_weights_drift_between_trades():
    index = pd.bdate_range("2024-01-01", periods=3)
    weights = pd.DataFrame({"A": [0.5], "B": [0.5]}, index=[index[0]])
    returns = pd.DataFrame({"A": [0.0, 0.10, 0.10], "B": [0.0, 0.0, 0.0]}, index=index)
    sim = simulate_clone(weights, returns, pd.Series(0.0, index=index))
    # day 2: A is 0.55 of 1.05 NAV, so its 10% move adds 0.055 / 1.05
    assert sim.returns.tolist() == pytest.approx([0.05, 0.055 / 1.05])


def test_clone_returns_never_depend_on_later_fund_returns():
    assets, rf = market()
    rng = np.random.default_rng(5)
    fund = assets @ np.array([0.4, 0.3, 0.2, 0.1]) + rng.normal(0, 0.003, len(assets))
    config = ReplicationConfig(window=120)
    base = walk_forward(fund, assets, rf, config)

    cut = base.returns.index[300]
    later = fund.index >= cut
    shocked = fund.copy()
    shocked[later] += rng.normal(0, 0.05, later.sum())
    alt = walk_forward(shocked, assets, rf, config)

    up_to_cut = base.returns.index <= cut
    pd.testing.assert_series_equal(base.returns[up_to_cut], alt.returns[up_to_cut])
    assert not np.allclose(base.returns[~up_to_cut], alt.returns[~up_to_cut])


def test_walk_forward_reports_only_returns_after_the_first_trade():
    assets, rf = market()
    fund = assets @ np.array([0.25, 0.25, 0.25, 0.25])
    result = walk_forward(fund, assets, rf, ReplicationConfig(window=120, cost_bps=0))
    first_trade = result.weights.index[0]
    assert result.returns.index[0] > first_trade
    assert first_trade > assets.index[120]  # signal after a full window, traded a day later
    assert result.weights.iloc[-1].to_numpy() == pytest.approx(np.full(4, 0.25), abs=1e-4)
    assert result.cash.abs().max() < 1e-4


def test_weekly_fit_recovers_weights_and_stays_causal():
    assets, rf = market()
    w_true = np.array([0.4, 0.3, 0.2, 0.1])
    config = ReplicationConfig(window=250, frequency="weekly")
    base = walk_forward(assets @ w_true, assets, rf, config)
    # compounding makes weekly fund returns only approximately linear in the ETF returns
    assert base.weights.iloc[-1].to_numpy() == pytest.approx(w_true, abs=0.02)

    cut = base.returns.index[300]
    shocked = assets @ w_true
    later = shocked.index >= cut
    shocked[later] += np.random.default_rng(6).normal(0, 0.05, later.sum())
    alt = walk_forward(shocked, assets, rf, config)
    up_to_cut = base.returns.index <= cut
    pd.testing.assert_series_equal(base.returns[up_to_cut], alt.returns[up_to_cut])


def test_etfs_join_the_clone_once_they_have_a_full_window():
    assets, rf = market()
    fund = assets @ np.array([0.25, 0.25, 0.25, 0.25])
    late = assets.copy()
    late.loc[late.index < late.index[400], "D"] = np.nan  # D starts trading on day 400
    result = walk_forward(fund, late, rf, ReplicationConfig(window=120, cost_bps=0))
    # eligible at the first signal whose window starts on day 400 or later, traded a day later
    too_early = result.weights.index <= late.index[400 + 120]
    assert (result.weights.loc[too_early, "D"] == 0).all()
    assert result.weights["D"].iloc[-1] == pytest.approx(0.25, abs=1e-3)
    assert result.returns.notna().all()


@pytest.mark.parametrize(
    "bad",
    [
        {"max_etfs": 0},
        {"max_etfs": 2.5},
        {"max_etfs": 3, "long_only": False},
        {"window": 5},
        {"window": 300.5},
        {"rebalance": "W"},
        {"min_weight": 1.0},
        {"financing_spread": -0.01},
    ],
)
def test_config_rejects_settings_it_cannot_honour(bad):
    with pytest.raises(ValueError, match="Invalid replication settings"):
        ReplicationConfig(**bad)


def test_walk_forward_defaults_to_the_estimator_the_app_uses():
    assets, rf = market()
    fund = assets @ np.array([0.4, 0.3, 0.2, 0.1])
    config = ReplicationConfig(window=120)
    default = walk_forward(fund, assets, rf, config)
    explicit = walk_forward(fund, assets, rf, config, make_estimator(config))
    pd.testing.assert_frame_equal(default.weights, explicit.weights)


def test_annual_turnover_counts_calendar_years():
    days = pd.bdate_range("2020-01-01", "2021-12-31")
    weights = pd.DataFrame({"A": [0.5, 0.6, 0.5]}, index=[days[0], days[200], days[400]])
    turnover = pd.Series([0.5, 0.2, 0.2], index=weights.index)
    returns = pd.Series(0.0, index=days[2::2])  # every other day merged away
    result = ReplicationResult(weights, returns, turnover, ReplicationConfig())
    years = (days[-1] - days[0]).days / 365.25
    assert result.annual_turnover == pytest.approx(0.4 / years)


def test_sales_realise_gains_at_average_cost():
    index = pd.bdate_range("2024-01-01", periods=4)
    weights = pd.DataFrame({"A": [1.0, 0.5], "B": [0.0, 0.5]}, index=[index[0], index[2]])
    returns = pd.DataFrame({"A": [0.0, 0.2, 0.0, 0.0], "B": 0.0}, index=index)
    sim = simulate_clone(weights, returns, pd.Series(0.0, index=index))
    # A, bought for 1, grows to 1.2; selling half of it realises half of the 0.2 gain
    assert sim.realised.tolist() == pytest.approx([0.0, 0.1 / 1.2])
    config = ReplicationConfig()
    result = ReplicationResult(weights, sim.returns, sim.turnover, config, sim.realised)
    years = (index[-1] - index[0]).days / 365.25
    assert result.annual_realised_gains == pytest.approx(0.1 / 1.2 / years)


def test_custom_estimator_gets_the_previous_weights():
    assets, rf = market()
    seen = []

    def equal_weight(y, X, previous, config):
        seen.append(previous.copy())
        return np.full(X.shape[1], 1.0 / X.shape[1])

    walk_forward(assets.mean(axis=1), assets, rf, ReplicationConfig(window=120), equal_weight)
    assert np.allclose(seen[0], 0.0)
    assert np.allclose(seen[1], 0.25)
