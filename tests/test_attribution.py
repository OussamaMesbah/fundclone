import numpy as np
import pandas as pd
import pytest

from factorlens.attribution import bond_factors, factor_regression, newey_west_lags, rolling_betas

TRUE_BETAS = np.array([1.0, 0.4, -0.2])
TRUE_ALPHA = 0.002  # per month


@pytest.fixture
def synthetic():
    rng = np.random.default_rng(0)
    n = 240
    index = pd.date_range("2000-01-31", periods=n, freq="ME")
    factors = pd.DataFrame(
        rng.normal(0.005, 0.04, size=(n, 3)), index=index, columns=["Mkt-RF", "HML", "MOM"]
    )
    y = TRUE_ALPHA + factors.to_numpy() @ TRUE_BETAS + rng.normal(0, 0.01, n)
    return pd.Series(y, index=index), factors


def test_regression_recovers_loadings_and_alpha(synthetic):
    y, factors = synthetic
    result = factor_regression(y, factors, periods_per_year=12)
    assert result.betas.to_numpy() == pytest.approx(TRUE_BETAS, abs=0.05)
    assert result.alpha == pytest.approx(TRUE_ALPHA * 12, abs=0.01)
    assert result.r_squared > 0.9
    assert result.n_obs == 240
    assert result.hac_lags == newey_west_lags(240)


def test_contributions_add_up_to_mean_excess_return(synthetic):
    y, factors = synthetic
    result = factor_regression(y, factors, periods_per_year=12)
    assert result.contributions.sum() == pytest.approx(y.mean() * 12)
    assert result.contributions["Alpha"] == pytest.approx(result.alpha)
    assert result.table().loc["Alpha", "Contribution p.a."] == pytest.approx(result.alpha)


def test_last_rolling_window_matches_full_sample(synthetic):
    y, factors = synthetic
    rolling = rolling_betas(y, factors, window=len(y))
    assert rolling.iloc[-1].to_numpy() == pytest.approx(
        factor_regression(y, factors).betas.to_numpy()
    )


def test_rolling_betas_empty_when_window_exceeds_sample(synthetic):
    y, factors = synthetic
    assert rolling_betas(y, factors, window=len(y) + 1).empty


def test_regression_needs_enough_observations(synthetic):
    y, factors = synthetic
    with pytest.raises(ValueError):
        factor_regression(y.iloc[:10], factors)


def test_bond_factors():
    index = pd.date_range("2020-01-31", periods=2, freq="ME")
    ief = pd.Series([0.01, 0.02], index)
    lqd = pd.Series([0.015, 0.01], index)
    rf = pd.Series([0.001, 0.001], index)
    out = bond_factors(ief, lqd, rf)
    assert out["TERM"].tolist() == pytest.approx([0.009, 0.019])
    assert out["DEF"].tolist() == pytest.approx([0.005, -0.01])


def test_newey_west_lags():
    assert newey_west_lags(100) == 4
    assert newey_west_lags(2500) == 8
