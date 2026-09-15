import pytest

from fundclone import etfs
from fundclone.factsheet import is_valid_isin


def test_catalogue_has_unique_tickers_and_plausible_costs():
    assert len(etfs.ETFS) == len(etfs.BY_TICKER)
    # Xetra-Gold alone takes no fee from its price
    assert all(0 < etf.expense_ratio < 0.01 for etf in etfs.ETFS if etf.ticker != "4GLD.DE")
    groups = {etf.asset_class for etf in etfs.ETFS}
    assert groups == {name for etf_set in etfs.SETS for name in etfs.asset_classes(etf_set)}
    assert not set(etfs.asset_classes("US")) & set(etfs.asset_classes("UCITS"))


def test_ucits_etfs_trade_in_euros_on_xetra_with_valid_isins():
    ucits = [etf for etf in etfs.ETFS if etf.etf_set == etfs.UCITS]
    assert len(ucits) == 47
    assert all(etf.currency == "EUR" and etf.ticker.endswith(".DE") for etf in ucits)
    assert all(is_valid_isin(etf.isin) for etf in ucits)
    assert len({etf.isin for etf in ucits}) == len(ucits)


def test_every_equity_group_has_a_us_share():
    equity = {"World equity", "US equity (UCITS)", "European equity", "Asia-Pacific equity"}
    assert equity | {"Emerging markets (UCITS)", "World factors", "World sectors"} <= set(
        etfs.US_SHARE
    )
    assert "EUR bonds" not in etfs.US_SHARE and "Global bonds" not in etfs.US_SHARE


def test_weighted_expense_ratio_charges_nothing_for_cash():
    assert etfs.expense_ratio({"SPY": 0.5, "AGG": 0.3}) == pytest.approx(
        0.5 * 0.000945 + 0.3 * 0.0003
    )


def test_filter_and_group_by_asset_class():
    bonds = etfs.tickers(["Bonds"])
    assert "AGG" in bonds and "SPY" not in bonds
    assert etfs.asset_class_weights({"SPY": 0.6, "AGG": 0.3, "TLT": 0.1}) == pytest.approx(
        {"US equity": 0.6, "Bonds": 0.4}
    )


def test_a_world_group_counts_as_partly_international(monkeypatch):
    monkeypatch.setitem(etfs.US_SHARE, "World equity", 0.7)
    weights = {"World equity": 0.5, "US equity": 0.3, "Bonds": 0.2}
    assert etfs.equity_weight(weights) == pytest.approx(0.8)
    assert etfs.international_weight(weights) == pytest.approx(0.15)


def test_the_default_set_is_the_us_listed_etfs():
    assert etfs.ASSET_CLASSES == etfs.asset_classes("US")
    assert (
        etfs.tickers()
        == etfs.tickers(etf_set="US")
        == [etf.ticker for etf in etfs.ETFS if etf.etf_set == "US"]
    )
    assert all(etf.currency == "USD" for etf in etfs.ETFS if etf.etf_set == "US")


def test_known_xetra_price_errors_are_left_out():
    import pandas as pd

    dates = pd.bdate_range("2010-10-25", "2017-06-09")
    prices = pd.DataFrame({"SXR8.DE": 1.0, "IS3Q.DE": 1.0, "EUNL.DE": 1.0}, index=dates)
    fixed = etfs.without_known_errors(prices)
    assert fixed.loc[:"2010-10-29", "SXR8.DE"].isna().all()
    assert fixed.loc["2010-11-01":, "SXR8.DE"].notna().all()
    assert pd.isna(fixed.loc["2017-06-05", "IS3Q.DE"])
    assert fixed.loc["2017-06-06", "IS3Q.DE"] == 1.0
    assert fixed["EUNL.DE"].notna().all()  # its start date lies before these prices
    assert prices.notna().all().all()  # the input is left as it was


def test_every_ucits_twin_belongs_to_a_us_etf_and_has_a_valid_isin():
    us = set(etfs.tickers())
    assert len(etfs.UCITS_TWINS) == 64
    for ticker, twin in etfs.UCITS_TWINS.items():
        assert ticker in us
        assert is_valid_isin(twin.isin), ticker
        assert 0 <= twin.expense_ratio < 0.01
        assert twin.match in ("same", "capped", "similar")


def test_twin_coverage_splits_the_clone_by_how_closely_its_twins_match():
    cover = etfs.twin_coverage({"SPY": 0.5, "VIG": 0.2, "KRE": 0.2})
    assert cover["same"] == pytest.approx(0.5 / 0.9)
    assert cover["similar"] == pytest.approx(0.2 / 0.9)
    assert cover["none"] == pytest.approx(0.2 / 0.9)
    assert cover["expense_ratio"] == pytest.approx((0.5 * 0.0007 + 0.2 * 0.0033) / 0.7)
    assert etfs.UCITS_TWINS["XLK"].describe().startswith("Same index, capped differently")
