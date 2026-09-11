"""Smoke tests: every chart builds from synthetic results in both colour modes."""

import numpy as np
import pandas as pd
import pytest

pytest.importorskip("plotly")

from factorlens import charts  # noqa: E402
from factorlens.attribution import factor_regression, rolling_betas  # noqa: E402
from factorlens.replication import ReplicationConfig, walk_forward  # noqa: E402

LABELS = {"fund": "FUND", "clone": "ETF clone", "closest": "SPY"}


@pytest.fixture(scope="module")
def results():
    rng = np.random.default_rng(0)
    months = pd.date_range("2005-01-31", periods=120, freq="ME")
    factors = pd.DataFrame(
        rng.normal(0.005, 0.04, (120, 3)), index=months, columns=["Mkt-RF", "HML", "MOM"]
    )
    y = factors @ np.array([1.0, 0.3, -0.1]) + rng.normal(0, 0.01, 120)

    days = pd.bdate_range("2015-01-01", periods=600)
    assets = pd.DataFrame(
        rng.normal(0.0004, 0.01, (600, 3)), index=days, columns=["SPY", "IWM", "IEF"]
    )
    fund = assets @ np.array([0.5, 0.2, 0.2]) + rng.normal(0, 0.002, 600)
    config = ReplicationConfig(window=120, long_only=False, max_gross=1.5)
    replication = walk_forward(fund, assets, pd.Series(0.0001, index=days), config)
    dates = replication.returns.index
    returns = pd.DataFrame(
        {
            "fund": fund.reindex(dates),
            "clone": replication.returns,
            "closest": assets["SPY"].reindex(dates),
        }
    )
    return factor_regression(y, factors), rolling_betas(y, factors, 36), replication, returns


@pytest.mark.parametrize("mode", ["light", "dark"])
def test_every_chart_builds(results, mode):
    attribution, betas, replication, returns = results
    figures = [
        charts.allocation(pd.Series({"SPY": 0.6, "IEF": 0.4}), {"SPY": "S&P 500"}, mode),
        charts.loadings(attribution, mode),
        charts.contributions(attribution, mode),
        charts.rolling_loadings(betas, mode),
        charts.growth(returns, LABELS, replication.weights.index[0], mode),
        charts.drawdowns(returns, LABELS, mode),
        charts.rolling_tracking_error(returns, 252, mode),
        charts.weights(replication.weights, mode),
    ]
    assert all(len(figure.data) > 0 for figure in figures)


def test_weights_chart_shows_cash_only_when_it_is_used(results):
    replication = results[2]
    fully_invested = replication.weights.div(replication.weights.sum(axis=1), axis=0)
    assert "Cash" not in [trace.name for trace in charts.weights(fully_invested).data]
    half_cash = fully_invested / 2
    assert "Cash" in [trace.name for trace in charts.weights(half_cash).data]


def test_weights_chart_folds_small_positions_into_other():
    dates = pd.bdate_range("2024-01-01", periods=3)
    weights = pd.DataFrame(np.full((3, 10), 0.1), index=dates, columns=[f"E{i}" for i in range(10)])
    names = [trace.name for trace in charts.weights(weights).data]
    assert len(names) == charts.MAX_SERIES + 1
    assert names[-1] == "Other"
