import pytest

from factorlens import etfs


def test_catalogue_has_unique_tickers_and_plausible_costs():
    assert len(etfs.ETFS) == len(etfs.BY_TICKER)
    assert all(0 < etf.expense_ratio < 0.01 for etf in etfs.ETFS)
    assert {etf.asset_class for etf in etfs.ETFS} == set(etfs.ASSET_CLASSES)


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
