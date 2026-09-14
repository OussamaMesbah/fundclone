import json
import logging
from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest

from fundclone import data
from fundclone.data import (
    daily_returns,
    fx_ticker,
    monthly_returns,
    parse_french_csv,
    to_usd,
    weekly_returns,
)

MONTHLY_FILE = """This file was created using the 202607 CRSP database.
Missing data are indicated by -99.99 or -999.

,Mkt-RF,SMB,RF
202401,   1.00,  -0.50,    0.40
202402,   2.00,  -99.99,    0.41

 Annual Factors: January-December
,Mkt-RF,SMB,RF
2024,  10.00,   1.00,    5.00

Copyright 2026 Eugene F. Fama and Kenneth R. French
"""

DAILY_FILE = """This file was created by using the 202607 CRSP database.

,Mom
20240102,   0.55
20240103,  -1.10

Copyright 2026 Eugene F. Fama and Kenneth R. French
"""


def test_monthly_file_is_stamped_at_month_end_and_stops_before_annual_table():
    df = parse_french_csv(MONTHLY_FILE)
    assert list(df.columns) == ["Mkt-RF", "SMB", "RF"]
    assert list(df.index) == [pd.Timestamp("2024-01-31"), pd.Timestamp("2024-02-29")]
    assert df.loc["2024-01-31", "Mkt-RF"] == pytest.approx(0.01)
    assert df.loc["2024-02-29", "RF"] == pytest.approx(0.0041)
    assert pd.isna(df.loc["2024-02-29", "SMB"])


def test_daily_file():
    df = parse_french_csv(DAILY_FILE)
    assert list(df.columns) == ["Mom"]
    assert list(df.index) == [pd.Timestamp("2024-01-02"), pd.Timestamp("2024-01-03")]
    assert df["Mom"].tolist() == pytest.approx([0.0055, -0.011])


def test_file_without_data_is_rejected():
    with pytest.raises(ValueError):
        parse_french_csv("Nothing to see here.\n")


def test_monthly_returns_drop_incomplete_first_and_last_month():
    dates = pd.bdate_range("2024-01-15", "2024-04-10")
    prices = pd.Series(range(len(dates)), index=dates, dtype=float) + 100
    returns = monthly_returns(prices)
    assert list(returns.index) == [pd.Timestamp("2024-02-29"), pd.Timestamp("2024-03-31")]
    assert returns.iloc[0] == pytest.approx(prices["2024-02-29"] / prices["2024-01-31"] - 1)
    assert returns.iloc[1] == pytest.approx(prices["2024-03-29"] / prices["2024-02-29"] - 1)


def test_monthly_returns_keep_last_month_when_data_reaches_its_end():
    # 28 March 2024 was the last trading day of the month (Good Friday followed)
    prices = pd.Series(1.0, index=pd.bdate_range("2024-01-02", "2024-03-28")).cumsum()
    assert monthly_returns(prices).index[-1] == pd.Timestamp("2024-03-31")


def test_daily_returns_bridge_gaps():
    prices = pd.Series([100.0, None, 110.0, 99.0], index=pd.bdate_range("2024-01-01", periods=4))
    assert (1 + daily_returns(prices)).prod() == pytest.approx(0.99)


def test_weekly_returns_compound_within_weeks_ending_friday():
    returns = pd.Series(0.01, index=pd.bdate_range("2024-01-01", "2024-01-12"))
    weekly = weekly_returns(returns)
    assert list(weekly.index) == [pd.Timestamp("2024-01-05"), pd.Timestamp("2024-01-12")]
    assert weekly.tolist() == pytest.approx([1.01**5 - 1] * 2)


def test_fx_symbols():
    assert fx_ticker("USD") is None
    assert fx_ticker("EUR") == "EURUSD=X"
    assert fx_ticker("GBp") == "GBPUSD=X"


def test_to_usd_uses_last_known_rate():
    dates = pd.bdate_range("2024-01-01", periods=3)
    prices = pd.Series([10.0, 11.0, 12.0], index=dates)
    rates = pd.Series([1.1, 1.2], index=[dates[0], dates[2]])
    assert to_usd(prices, rates).tolist() == pytest.approx([11.0, 12.1, 14.4])


DATES = pd.bdate_range("2024-01-01", periods=5)


@pytest.fixture
def cache(tmp_path, monkeypatch):
    monkeypatch.setattr(data, "CACHE_DIR", tmp_path)
    calls = []

    def download(tickers):
        calls.append(list(tickers))
        return {t: pd.Series([1.0, 2.0, 3.0, 4.0, 5.0], index=DATES) for t in tickers}

    monkeypatch.setattr(data, "_download_closes", download)
    return calls


def test_prices_are_cached_on_disk(cache):
    first = data.fetch_prices(["AAA", "BBB"], "2024-01-01", "2024-01-06")
    second = data.fetch_prices(["BBB", "AAA"], "2024-01-02", "2024-01-06")
    assert cache == [["AAA", "BBB"]]
    assert list(second.columns) == ["BBB", "AAA"]
    assert list(second.index) == list(DATES[1:])
    assert second["AAA"].tolist() == first["AAA"].iloc[1:].tolist()


def test_stale_cache_is_used_when_the_download_fails(cache, monkeypatch):
    data.fetch_prices(["AAA"], "2024-01-01", "2024-01-06")
    monkeypatch.setattr(data, "PRICE_MAX_AGE", -1)  # everything is stale now
    monkeypatch.setattr(data, "_download_closes", lambda tickers: {})
    assert data.fetch_prices(["AAA"], "2024-01-01", "2024-01-06")["AAA"].tolist() == [
        1.0,
        2.0,
        3.0,
        4.0,
        5.0,
    ]


def test_damaged_price_cache_counts_as_missing(cache):
    path = data._cache_file("prices", "AAA", ".csv")
    path.parent.mkdir(parents=True)
    path.write_text("")  # as left behind by an interrupted write
    prices = data.fetch_prices(["AAA"], "2024-01-01", "2024-01-06")
    assert prices["AAA"].tolist() == [1.0, 2.0, 3.0, 4.0, 5.0]
    assert cache == [["AAA"]]


def test_damaged_info_cache_is_fetched_again(tmp_path, monkeypatch):
    monkeypatch.setattr(data, "CACHE_DIR", tmp_path)
    path = data._cache_file("info", "AAA", ".json")
    path.parent.mkdir(parents=True)
    path.write_text('{"name": "tru')
    raw = {
        "longName": "AAA Fund",
        "currency": "USD",
        "exchangeTimezoneName": "America/New_York",
        "quoteType": "MUTUALFUND",
        "netExpenseRatio": 0.59,
        "annualHoldingsTurnover": 0.32,
    }
    monkeypatch.setattr(data.yf, "Ticker", lambda ticker: SimpleNamespace(info=raw, fast_info={}))
    info = data.fetch_info("AAA")
    assert info == {
        "name": "AAA Fund",
        "currency": "USD",
        "timezone": "America/New_York",
        "quote_type": "MUTUALFUND",
        "expense_ratio": pytest.approx(0.0059),
        "turnover": pytest.approx(0.32),
    }
    assert json.loads(path.read_text())["name"] == "AAA Fund"


def test_a_cache_written_before_a_field_existed_is_fetched_again(tmp_path, monkeypatch):
    monkeypatch.setattr(data, "CACHE_DIR", tmp_path)
    path = data._cache_file("info", "AAA", ".json")
    path.parent.mkdir(parents=True)
    old = {"name": "AAA Fund", "currency": "USD", "timezone": None, "quote_type": "MUTUALFUND"}
    path.write_text(json.dumps(old | {"expense_ratio": 0.0059}))  # no "turnover" yet
    raw = {"longName": "AAA Fund", "annualHoldingsTurnover": 0.32}
    monkeypatch.setattr(data.yf, "Ticker", lambda ticker: SimpleNamespace(info=raw, fast_info={}))
    assert data.fetch_info("AAA")["turnover"] == pytest.approx(0.32)


def market_moves(n: int, seed: int) -> tuple[pd.DatetimeIndex, np.ndarray, pd.DataFrame]:
    rng = np.random.default_rng(seed)
    dates = pd.bdate_range("2023-01-02", periods=n)
    common = rng.normal(0, 0.01, n)
    etfs = pd.DataFrame({f"E{i}": common + rng.normal(0, 0.002, n) for i in range(5)}, dates)
    return dates, common, etfs


def test_stale_prices_are_dropped_only_where_the_fund_should_have_moved():
    dates, common, etfs = market_moves(300, seed=0)
    rng = np.random.default_rng(1)
    stock = pd.Series(100 * np.cumprod(1 + common + rng.normal(0, 0.002, 300)), dates)
    bond = pd.Series(100 * np.cumprod(1 + rng.normal(0, 0.002, 300)), dates)
    median = etfs.median(axis=1).abs()
    busy = list(median[dates[100:]][median > 0.01].index[:2])
    quiet = median[dates[100:]][median < 0.001].index[0]
    for fund in (stock, bond):
        for day in [*busy, quiet]:
            fund[day] = fund.shift(1)[day]  # the previous price, repeated
    # the stock fund should have moved on the busy days; the bond fund never follows stocks
    assert list(stock.index.difference(data.drop_stale_prices(stock, etfs).index)) == busy
    assert data.drop_stale_prices(bond, etfs).equals(bond)


def test_prices_that_jump_and_come_back_are_dropped():
    dates, _, etfs = market_moves(200, seed=2)
    fund = pd.Series(100 * np.cumprod(1 + np.random.default_rng(3).normal(0, 0.005, 200)), dates)
    glitch = fund.copy()
    glitch.iloc[50] *= 0.8  # one bad price, like BSCFX's on 4 January 2010
    glitch.iloc[120:122] /= 10  # a misplaced decimal point for two days
    cleaned = data.drop_price_errors(glitch, etfs)
    assert list(glitch.index.difference(cleaned.index)) == [dates[50], dates[120], dates[121]]
    assert data.drop_price_errors(fund, etfs).equals(fund)


def test_unreversed_jumps_are_reported_not_removed():
    dates, _, etfs = market_moves(200, seed=4)
    fund = pd.Series(100 * np.cumprod(1 + np.random.default_rng(5).normal(0, 0.01, 200)), dates)
    fund.iloc[100:] /= 10  # a ten-for-one split that was not adjusted
    assert data.drop_price_errors(fund, etfs).equals(fund)
    jumps = data.price_jumps(fund, etfs)
    assert list(jumps.index) == [dates[100]]
    assert jumps.iloc[0] == pytest.approx(-0.9, abs=0.05)


def test_volatile_series_keep_their_jumps():
    dates, _, etfs = market_moves(200, seed=6)
    stock = pd.Series(100 * np.cumprod(1 + np.random.default_rng(7).normal(0, 0.04, 200)), dates)
    stock.iloc[80] *= 1.9  # a squeeze that fades at once, like GME's in January 2021
    assert data.drop_price_errors(stock, etfs).equals(stock)
    assert data.price_jumps(stock, etfs).empty


def test_split_factors():
    assert data.split_factor(0.0994) == pytest.approx(0.1)
    assert data.split_factor(2.02) == 2
    assert data.split_factor(0.8) is None


def test_unadjusted_splits_are_undone():
    dates, _, etfs = market_moves(200, seed=4)
    fund = pd.Series(100 * np.cumprod(1 + np.random.default_rng(5).normal(0, 0.01, 200)), dates)
    split = fund.copy()
    split.iloc[100:] /= 10  # a ten-for-one split that Yahoo did not adjust for
    adjusted, found = data.adjust_splits(split, etfs)
    assert found == [(dates[100], pytest.approx(0.1), pytest.approx(-0.9, abs=0.03))]
    pd.testing.assert_series_equal(adjusted, fund / 10)


def test_interest_is_compounded_over_gaps_and_carried_forward():
    rates = pd.Series(0.001, index=pd.bdate_range("2024-01-01", "2024-01-10"))
    dates = pd.DatetimeIndex(["2024-01-02", "2024-01-05", "2024-01-08", "2024-01-15"])
    rf = data.compounded_rate(rates, dates)
    assert np.isnan(rf.iloc[0])
    assert rf.iloc[1] == pytest.approx(1.001**3 - 1)  # 3, 4 and 5 January
    assert rf.iloc[2] == pytest.approx(0.001)  # a Monday after a Friday
    assert rf.iloc[3] == pytest.approx(1.001**5 - 1)  # 9 to 15 January, from the 11th assumed


RATE_LIMIT_LOG = "['AAA']: YFRateLimitError('Too Many Requests. Rate limited. Try after a while.')"


def closes_frame(tickers):
    """What yf.download returns: columns (price field, ticker)."""
    closes = pd.DataFrame({ticker: [1.0, 2.0, 3.0] for ticker in tickers}, index=DATES[:3])
    return pd.concat({"Close": closes}, axis=1)


def test_a_rate_limit_is_waited_out_and_the_download_repeated(tmp_path, monkeypatch):
    monkeypatch.setattr(data, "CACHE_DIR", tmp_path)
    attempts, waits = [], []

    def download(tickers, **kwargs):
        attempts.append(tickers)
        if len(attempts) == 1:  # yfinance logs the limit instead of raising it
            logging.getLogger("yfinance").error(RATE_LIMIT_LOG)
            return pd.DataFrame()
        return closes_frame(tickers)

    monkeypatch.setattr(data.yf, "download", download)
    monkeypatch.setattr(data.time, "sleep", waits.append)
    prices = data.fetch_prices(["AAA"], "2024-01-01", "2024-01-06")
    assert prices["AAA"].tolist() == [1.0, 2.0, 3.0]
    assert waits == [data.RATE_LIMIT_WAITS[0]]
    assert "notes" not in prices.attrs


def test_a_lasting_rate_limit_says_so_instead_of_returning_nothing(tmp_path, monkeypatch):
    monkeypatch.setattr(data, "CACHE_DIR", tmp_path)
    waits = []

    def download(tickers, **kwargs):
        logging.getLogger("yfinance").error(RATE_LIMIT_LOG)
        return pd.DataFrame()

    monkeypatch.setattr(data.yf, "download", download)
    monkeypatch.setattr(data.time, "sleep", waits.append)
    with pytest.raises(data.YahooRateLimitError, match="no prices for AAA. Try again"):
        data.fetch_prices(["AAA"], "2024-01-01", "2024-01-06")
    assert waits == list(data.RATE_LIMIT_WAITS)


def test_during_a_rate_limit_earlier_prices_are_used_with_a_note(cache, monkeypatch):
    data.fetch_prices(["AAA"], "2024-01-01", "2024-01-06")  # fills the cache
    monkeypatch.setattr(data, "PRICE_MAX_AGE", -1)  # everything is stale now

    def limited(tickers):
        raise data.YahooRateLimitError()

    monkeypatch.setattr(data, "_download_closes", limited)
    prices = data.fetch_prices(["AAA"], "2024-01-01", "2024-01-06")
    assert prices["AAA"].tolist() == [1.0, 2.0, 3.0, 4.0, 5.0]
    assert "limiting requests" in prices.attrs["notes"][0]


def test_yahoo_symbols_for_an_isin(monkeypatch):
    quotes = [
        {
            "symbol": "HJUA.F",
            "longname": "DWS Top Dividende",
            "quoteType": "ETF",
            "exchDisp": "Frankfurt",
        },
        {"longname": "without a symbol"},
    ]
    monkeypatch.setattr(data.yf, "Search", lambda isin, max_results: SimpleNamespace(quotes=quotes))
    assert data.yahoo_symbols("DE0009848119") == [
        {"symbol": "HJUA.F", "name": "DWS Top Dividende", "type": "ETF", "exchange": "Frankfurt"}
    ]
    with pytest.raises(ValueError, match="not a valid ISIN"):
        data.yahoo_symbols("DE0009848118")  # wrong check digit


def test_yahoo_symbols_is_empty_when_the_search_fails(monkeypatch):
    def failing(isin, max_results):
        raise RuntimeError("rate limited")

    monkeypatch.setattr(data.yf, "Search", failing)
    assert data.yahoo_symbols("DE0009848119") == []
