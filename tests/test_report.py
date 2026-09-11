import math

import pytest
from fakes import analyse
from scipy import stats

from fundclone.report import _signed, closet_index_check, headline, interval, too_short


@pytest.fixture(scope="module")
def result():
    return analyse()


def test_interval_is_a_t_interval_for_the_log_gap_in_annual_returns(result):
    t = result.tracking
    low, high = interval(t)
    years = t["observations"] / t["periods_per_year"]
    half = stats.t.ppf(0.975, t["observations"] - 1) * t["active_risk"] / math.sqrt(years)
    base = 1 + t["clone_return"]
    assert low == pytest.approx(base * math.expm1(t["log_gap"] - half))
    assert high == pytest.approx(base * math.expm1(t["log_gap"] + half))
    assert low < t["active_return"] < high


def test_closet_index_check_applies_esma_thresholds(result, monkeypatch):
    monkeypatch.setattr(result, "equity_share", 0.9)
    monkeypatch.setattr(
        result, "benchmark_fit", {"tracking_error": 0.02, "r_squared": 0.97, "beta": 1.01}
    )
    assert closet_index_check(result)["flagged"]
    monkeypatch.setattr(
        result, "benchmark_fit", {"tracking_error": 0.02, "r_squared": 0.97, "beta": 1.10}
    )
    check = closet_index_check(result)
    assert not check["flagged"]
    assert check["checks"] == {
        "tracking error below 3%": True,
        "R² above 95%": True,
        "beta between 0.95 and 1.05": False,
    }


def test_closet_index_check_skips_bond_funds(result, monkeypatch):
    monkeypatch.setattr(result, "equity_share", 0.2)
    assert closet_index_check(result) is None


def test_closet_index_check_expects_index_funds_to_pass(result, monkeypatch):
    monkeypatch.setattr(result, "equity_share", 0.9)
    assert not closet_index_check(result)["passive"]  # "FUND Fund" charges 0.75%
    monkeypatch.setattr(result, "name", "Vanguard 500 Index Admiral")
    assert closet_index_check(result)["passive"]


def test_headline_reports_the_range_of_the_gap(result):
    low, high = interval(result.tracking)
    assert f"{_signed(low)} to {_signed(high)}" in headline(result)[2]


def test_a_short_sample_gets_no_range_no_closest_etf_and_no_annual_gap(result, monkeypatch):
    monkeypatch.setitem(result.tracking, "observations", 20)
    lines = headline(result)
    assert lines[0].startswith("There are only 20 weeks of out-of-sample returns")
    assert not any("95% range" in line or "closest single ETF" in line for line in lines)


def test_less_than_a_calendar_year_is_short_even_with_52_weeks(result, monkeypatch):
    monkeypatch.setattr(result, "equity_share", 0.9)
    monkeypatch.setattr(result, "returns", result.returns.iloc[-250:])
    assert too_short(result)
    assert closet_index_check(result) is None


def test_signed_never_prints_minus_zero():
    assert _signed(-0.0003) == "+0.0%"
    assert _signed(-0.012) == "-1.2%"


def test_closet_index_check_needs_a_year_of_returns(result, monkeypatch):
    monkeypatch.setattr(result, "equity_share", 0.9)
    monkeypatch.setitem(result.tracking, "observations", 20)
    assert closet_index_check(result) is None


def test_headline_of_a_clone_in_t_bills(result, monkeypatch):
    monkeypatch.setattr(result.replication, "weights", result.replication.weights * 0)
    assert headline(result)[0].startswith("A clone in T-bills explains")


def test_headline_when_only_the_latest_clone_is_in_t_bills(result, monkeypatch):
    weights = result.replication.weights.copy()
    weights.iloc[-1] = 0.0
    monkeypatch.setattr(result.replication, "weights", weights)
    assert headline(result)[0].startswith("The clone, in T-bills since its latest rebalance,")
