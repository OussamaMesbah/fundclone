import time

import numpy as np
import pandas as pd
import pytest

from fundclone.cli import looks_like_portfolio
from fundclone.portfolio import (
    format_portfolio,
    parse_portfolio,
    portfolio_returns,
    whole_shares,
)


def test_parse_accepts_several_formats_and_normalises():
    assert parse_portfolio("VTI 60, vxus: 30%\nBND 10") == pytest.approx(
        {"VTI": 0.6, "VXUS": 0.3, "BND": 0.1}
    )
    assert parse_portfolio("SPY 1; SPY 1; AGG 2") == pytest.approx({"SPY": 0.5, "AGG": 0.5})
    assert parse_portfolio("EXS1.DE 50, BRK-B 50") == pytest.approx({"EXS1.DE": 0.5, "BRK-B": 0.5})
    assert parse_portfolio("vti 60 bnd 40") == pytest.approx({"VTI": 0.6, "BND": 0.4})
    tokyo_hong_kong = parse_portfolio("7203.T 50 0700.HK: 50%")
    assert tokyo_hong_kong == pytest.approx({"7203.T": 0.5, "0700.HK": 0.5})
    assert parse_portfolio("^GSPC 60, AGG 40 %") == pytest.approx({"^GSPC": 0.6, "AGG": 0.4})


def test_a_long_line_with_a_typo_fails_fast():
    started = time.perf_counter()
    with pytest.raises(ValueError, match="Cannot read"):
        parse_portfolio("VTI 1 " * 40 + "BND")
    assert time.perf_counter() - started < 0.5
    with pytest.raises(ValueError, match="characters"):
        parse_portfolio("VTI 1, " * 1000)


@pytest.mark.parametrize("text", ["", "VTI", "VTI sixty", "VTI 0", "VTI 60 40"])
def test_parse_rejects_bad_input(text):
    with pytest.raises(ValueError):
        parse_portfolio(text)


def test_format_round_trips():
    weights = {"VTI": 0.6, "BND": 0.4}
    assert parse_portfolio(format_portfolio(weights)) == pytest.approx(weights)


def test_portfolio_or_ticker():
    assert looks_like_portfolio("VTI 60, BND 40")
    assert looks_like_portfolio("VTI:100")
    assert not looks_like_portfolio("EXS1.DE")
    assert not looks_like_portfolio("BRK-B")


def test_returns_are_the_weighted_daily_returns_once_every_holding_trades():
    dates = pd.bdate_range("2024-01-01", periods=4)
    prices = pd.DataFrame({"A": [100, 110, 121, 121.0], "B": [np.nan, 50, 55, 44.0]}, index=dates)
    returns = portfolio_returns(prices, {"A": 0.5, "B": 0.5})
    assert list(returns.index) == list(dates[2:])
    assert returns.tolist() == pytest.approx([0.1, -0.1])


def test_whole_shares_keep_small_positions():
    shares = whole_shares({"SOXX": 0.034, "IWF": 0.9}, {"SOXX": 517.0, "IWF": 100.0}, 10_000)
    assert shares == {"SOXX": 1, "IWF": 90}  # rounding down would leave SOXX empty


def test_whole_shares_never_spend_more_than_the_amount():
    prices = {"A": 333.0, "B": 77.0, "C": 1250.0}
    shares = whole_shares({"A": 0.4, "B": 0.35, "C": 0.25}, prices, 5_000)
    assert sum(n * prices[t] for t, n in shares.items()) <= 5_000
    assert whole_shares({"A": 1.0, "Z": 0.0}, {"A": 10.0}, 100) == {"A": 10, "Z": 0}


def test_missing_holding_raises():
    with pytest.raises(ValueError, match="ZZZ"):
        portfolio_returns(pd.DataFrame({"A": [1.0, 2.0]}), {"A": 0.5, "ZZZ": 0.5})
