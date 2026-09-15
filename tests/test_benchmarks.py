"""Helpers of the benchmark harness."""

import numpy as np

from benchmarks.run import median_range


def test_median_range_brackets_the_median_and_is_reproducible():
    values = np.linspace(0.01, 0.05, 23)
    low, high = median_range(values)
    assert low < np.median(values) < high
    assert median_range(values) == (low, high)


def test_median_range_of_identical_values_is_that_value():
    assert median_range([0.03] * 10) == (0.03, 0.03)


def test_traded_by_keeps_the_etfs_an_investor_could_have_known_then():
    import pandas as pd

    from benchmarks.run import universe_for

    dates = pd.bdate_range("2008-01-01", periods=400)
    prices = pd.DataFrame({"SPY": 1.0, "XLRE": 1.0, "QQQ": 1.0}, index=dates)
    prices.loc[:"2009-06-30", "XLRE"] = None  # starts trading later
    chosen = universe_for("traded-by:2009-01-02", "", prices)
    assert "SPY" in chosen and "QQQ" in chosen
    assert "XLRE" not in chosen


def test_paired_compares_fund_by_fund_over_the_funds_both_runs_scored():
    import pandas as pd
    import pytest

    from benchmarks.compare import paired

    first = pd.DataFrame(
        {
            "ticker": ["A", "B", "C", "D"],
            "te_weekly": [0.04, 0.05, 0.03, 0.06],
            "error": ["", "", "", "ValueError: no data"],
        }
    )
    second = pd.DataFrame(
        {"ticker": ["A", "B", "C", "E"], "te_weekly": [0.03, 0.04, 0.035, 0.01], "error": ""}
    )
    result = paired(first, second)
    assert result["funds"] == 3  # D failed in the first run, E is only in the second
    assert result["median"] == pytest.approx(0.01)
    assert result["positive"] == 2
    assert result["low"] <= result["median"] <= result["high"]
    # two figures of one run: the closest single ETF against the clone
    run = first.assign(te_closest=[0.05, 0.05, 0.05, 0.05])
    assert paired(run, run, "te_closest", "te_weekly")["median"] == pytest.approx(0.01)


def test_verdicts_count_the_active_funds_ahead_and_behind_by_more_than_noise():
    import pandas as pd

    from benchmarks.run import verdicts

    ok = pd.DataFrame(
        {
            "category": ["US large-cap", "Bond", "Index", "Sector"],
            "gap": [0.01, -0.02, 0.0, 0.03],
            "gap_low": [-0.01, -0.03, -0.001, 0.005],
            "gap_high": [0.03, -0.005, 0.001, 0.05],
            "gap_closest": [-0.01, -0.02, 0.0, 0.02],
            "gap_closest_low": [-0.03, -0.04, -0.001, -0.01],
            "gap_closest_high": [0.01, -0.001, 0.001, 0.05],
        }
    )
    text = verdicts(ok)
    assert "3 active funds" in text  # the index fund is left out
    assert "against the clone: ahead 2, by more than noise 1; behind by more than noise 1" in text
    closest = "against the closest single ETF: ahead 1, by more than noise 0; behind by"
    assert f"{closest} more than noise 1" in text
