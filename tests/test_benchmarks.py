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
