import numpy as np
import pandas as pd
import pytest

from factorlens.metrics import benchmark_fit, drawdown, performance, tracking, years_spanned


def test_benchmark_fit_recovers_beta_and_r_squared():
    rng = np.random.default_rng(3)
    benchmark = pd.Series(rng.normal(0, 0.02, 1000))
    fund = 1.2 * benchmark + pd.Series(rng.normal(0, 0.002, 1000))
    fit = benchmark_fit(fund, benchmark, 52)
    assert fit["beta"] == pytest.approx(1.2, abs=0.02)
    assert fit["r_squared"] == pytest.approx(fund.corr(benchmark) ** 2)
    assert fit["tracking_error"] == pytest.approx((fund - benchmark).std() * np.sqrt(52))


def test_drawdown_counts_losses_from_the_initial_capital():
    dd = drawdown(pd.Series([-0.1, 0.05, -0.2]))
    assert dd.iloc[0] == pytest.approx(-0.1)
    assert dd.min() == pytest.approx(0.9 * 1.05 * 0.8 - 1)


def test_performance_annualises_geometrically():
    returns = pd.Series(np.full(504, 0.001))
    stats = performance(returns, pd.Series(np.zeros(504)))
    assert stats["annual_return"] == pytest.approx(1.001**252 - 1)
    assert stats["total_return"] == pytest.approx(1.001**504 - 1)
    assert stats["max_drawdown"] == 0
    assert np.isnan(stats["sharpe"])  # no volatility


def test_performance_counts_calendar_years_when_days_are_merged():
    dates = pd.bdate_range("2020-01-01", periods=505)[1:]
    daily = pd.Series(0.001, index=dates)
    pairs = (1 + daily).groupby(np.arange(len(daily)) // 2).prod() - 1
    merged = pd.Series(pairs.to_numpy(), index=dates[1::2])  # every second day merged away
    rf = pd.Series(0.0, index=dates)
    assert performance(merged, rf)["annual_return"] == pytest.approx(
        performance(daily, rf)["annual_return"], rel=5e-3
    )


def test_performance_does_not_annualise_less_than_a_year():
    dates = pd.bdate_range("2024-01-01", periods=30)
    stats = performance(pd.Series(0.01, dates), pd.Series(0.0, dates))
    assert np.isnan(stats["annual_return"])
    assert stats["total_return"] == pytest.approx(1.01**30 - 1)


def test_a_fund_that_never_moves_has_no_r_squared():
    clone = pd.Series(np.random.default_rng(2).normal(0, 0.01, 60))
    stats = tracking(pd.Series(0.0, index=clone.index), clone, 52)
    assert np.isnan(stats["r_squared"])
    assert np.isnan(stats["correlation"])


def test_years_spanned():
    assert years_spanned(pd.bdate_range("2020-01-01", "2021-12-31")) == pytest.approx(2, abs=0.01)
    assert years_spanned(pd.RangeIndex(504)) == 2.0


def test_tracking_of_identical_series():
    r = pd.Series(np.random.default_rng(0).normal(0, 0.01, 500))
    stats = tracking(r, r)
    assert stats["tracking_error"] == 0
    assert stats["r_squared"] == 1
    assert stats["correlation"] == pytest.approx(1)
    assert np.isnan(stats["active_tstat"])


def test_tracking_of_a_noisy_clone():
    rng = np.random.default_rng(1)
    fund = pd.Series(rng.normal(0.0005, 0.01, 2000))
    clone = fund - 0.0001 + pd.Series(rng.normal(0, 0.005, 2000))
    stats = tracking(fund, clone)
    gap = np.log1p(fund) - np.log1p(clone)
    assert stats["tracking_error"] == pytest.approx(0.005 * np.sqrt(252), rel=0.05)
    assert stats["active_return"] == pytest.approx(0.0001 * 252, abs=0.03)
    assert stats["active_return"] == stats["fund_return"] - stats["clone_return"]
    assert stats["log_gap"] == pytest.approx(gap.mean() * 252)
    assert stats["active_risk"] == pytest.approx(gap.std() * np.sqrt(252))
    assert stats["active_tstat"] == pytest.approx(gap.mean() / gap.std() * np.sqrt(2000))
    assert 0.6 < stats["r_squared"] < 0.9


def test_active_return_is_the_gap_in_compound_growth():
    # the fund swings while the clone grows smoothly, and both end with the same wealth
    fund = pd.Series([0.05, 1.001**2 / 1.05 - 1] * 100)
    clone = pd.Series(0.001, index=fund.index)
    assert (1 + fund).prod() == pytest.approx((1 + clone).prod())
    assert tracking(fund, clone, 52)["active_return"] == pytest.approx(0.0, abs=1e-12)
    assert (fund - clone).mean() * 52 > 0.05  # the arithmetic mean would credit the fund


def test_active_return_is_a_difference_of_annual_returns_even_for_large_losses():
    weeks = pd.RangeIndex(104)
    stats = tracking(pd.Series(-0.01, weeks), pd.Series(0.0, weeks), 52)
    assert stats["active_return"] == pytest.approx(0.99**52 - 1)  # not the log gap of -52%
