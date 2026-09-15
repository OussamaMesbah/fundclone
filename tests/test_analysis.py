"""End-to-end runs of the pipeline on synthetic data, without network access."""

import numpy as np
import pandas as pd
import pytest
from fakes import CONFIG, DATES, SMALL, analyse, fake_factors, fake_info, fake_prices

from fundclone import etfs
from fundclone.analysis import _region_for, run_analysis
from fundclone.data import FF6
from fundclone.replication import ReplicationConfig
from fundclone.report import headline


def test_fund_pipeline_on_synthetic_data():
    a = analyse()
    assert (a.label, a.name, a.expense_ratio) == ("FUND", "FUND Fund", 0.0075)
    assert a.attribution.n_obs == 59  # February 2010 to December 2014
    assert a.closest_etf in etfs.tickers(SMALL)
    assert set(a.performance.index) == {"FUND", "ETF clone", a.closest_etf}
    assert list(a.returns.columns) == ["fund", "clone", "closest", "rf"]
    assert a.returns.index[0] > a.replication.weights.index[0]
    assert (a.replication.weights >= -1e-9).all().all()
    assert (a.replication.gross_exposure <= 1 + 1e-9).all()
    assert a.replication.config.frequency == "daily"
    assert a.tracking_periods_per_year == 52  # tracking is always measured on weekly returns
    assert a.allocation()["Weight"].sum() == pytest.approx(1.0)
    assert 0 <= a.clone_expense_ratio < 0.01
    assert 0 <= a.equity_share <= 1
    assert set(a.benchmark_fit) == {"beta", "r_squared", "tracking_error"}
    assert a.notes == []
    assert len(headline(a)) == 4


def test_bond_factors_join_the_model_when_asked():
    a = analyse(asset_classes=["Bonds"], use_bond_factors=True)
    assert list(a.attribution.betas.index) == [*FF6, "TERM", "DEF"]
    assert list(a.replication.weights.columns) == etfs.tickers(["Bonds"])
    assert a.equity_share == 0


def test_foreign_currency_fund_is_converted_and_fitted_weekly():
    requested = []

    def loader(tickers, start, end):
        requested.extend(tickers)
        return fake_prices(tickers, start, end)

    a = analyse("FUND.DE", price_loader=loader)
    assert "EURUSD=X" in requested
    assert a.currency == "EUR"
    assert a.replication.config.frequency == "weekly"
    assert a.tracking_periods_per_year == 52
    assert a.tracking_returns.index.dayofweek.unique().tolist() == [4]  # Fridays
    assert any("EUR" in note for note in a.notes)


def test_custom_portfolio_is_a_constant_mix_of_its_holdings():
    seen = {}

    def loader(tickers, start, end):
        seen["prices"] = fake_prices(tickers, start, end)
        return seen["prices"]

    a = analyse({"aaa": 60, "BBB": 40}, price_loader=loader)
    assert a.label == "Portfolio"
    assert a.holdings == pytest.approx({"AAA": 0.6, "BBB": 0.4})
    held = seen["prices"][["AAA", "BBB"]]
    expected = (held / held.shift(1) - 1).dropna() @ pd.Series({"AAA": 0.6, "BBB": 0.4})
    pd.testing.assert_series_equal(
        a.returns["fund"], expected.reindex(a.returns.index), check_names=False, check_freq=False
    )


def test_unknown_ticker_raises():
    with pytest.raises(ValueError, match="No price data"):
        analyse(price_loader=lambda tickers, start, end: fake_prices(tickers[1:], start, end))


def test_the_fund_itself_is_not_a_building_block():
    a = analyse("SPY", asset_classes=["US equity"])
    assert "SPY" not in a.replication.weights.columns
    assert any("SPY itself" in note for note in a.notes)


def test_max_etfs_caps_the_clone():
    a = analyse(replication=ReplicationConfig(window=126, max_etfs=3))
    assert ((a.replication.weights > 1e-6).sum(axis=1) <= 3).all()


def test_stale_fund_prices_are_merged_with_the_next_day():
    def loader(tickers, start, end):
        prices = fake_prices(tickers, start, end)
        moves = (prices / prices.shift(1) - 1).drop(columns="FUND").median(axis=1).abs()
        day = moves[(moves > 0.01) & (moves.index > moves.index[100])].index[0]
        prices.loc[day, "FUND"] = prices["FUND"].shift(1)[day]
        return prices

    a = analyse(price_loader=loader)
    assert any("FUND's price did not change" in note for note in a.notes)


def test_notes_from_the_price_loader_are_passed_on():
    def loader(tickers, start, end):
        prices = fake_prices(tickers, start, end)
        prices.attrs["notes"] = ["Prices come from a snapshot."]
        return prices

    assert "Prices come from a snapshot." in analyse(price_loader=loader).notes


def test_a_one_day_price_error_is_left_out_with_a_note():
    def loader(tickers, start, end):
        prices = fake_prices(tickers, start, end)
        prices.iloc[300, prices.columns.get_loc("FUND")] *= 0.5
        return prices

    a = analyse(price_loader=loader)
    assert any("it looks like a data error and is left out" in note for note in a.notes)


def test_a_stock_keeps_its_big_moves():
    def info(ticker):
        return {**fake_info(ticker), "quote_type": "EQUITY"}

    def loader(tickers, start, end):
        prices = fake_prices(tickers, start, end)
        prices.iloc[:600, prices.columns.get_loc("FUND")] *= 2  # a genuine halving
        return prices

    a = analyse(price_loader=loader, info_loader=info)
    assert not any("split" in note for note in a.notes)
    assert a.returns["fund"].min() < -0.4


def test_a_portfolio_with_a_money_market_fund_raises():
    def loader(tickers, start, end):
        return fake_prices(tickers, start, end).assign(MMF=1.0)

    with pytest.raises(ValueError, match="MMF on Yahoo Finance never changes"):
        analyse({"AAA": 60, "MMF": 40}, price_loader=loader)


def test_a_price_index_gets_a_note_about_dividends():
    a = analyse({"^GSPC": 60, "BBB": 40})
    assert any("^GSPC is a price index without dividends" in note for note in a.notes)


def test_an_unadjusted_split_is_undone_with_a_note():
    def loader(tickers, start, end):
        prices = fake_prices(tickers, start, end)
        prices.iloc[:600, prices.columns.get_loc("FUND")] *= 10  # prices before a 10-for-1 split
        return prices

    a = analyse(price_loader=loader)
    assert any("10-for-1 split" in note for note in a.notes)
    assert a.returns["fund"].abs().max() < 0.2


def test_a_recent_unadjusted_distribution_ends_the_figures_before_it():
    def loader(tickers, start, end):
        prices = fake_prices(tickers, start, end)
        prices.iloc[-3:, prices.columns.get_loc("FUND")] *= 0.9  # paid out, not adjusted
        return prices

    a = analyse(price_loader=loader)
    assert any("before Yahoo Finance adjusts" in note for note in a.notes)
    assert a.returns.index[-1] == DATES[-4]


def test_a_fund_whose_price_never_changes_raises():
    def loader(tickers, start, end):
        return fake_prices(tickers, start, end).assign(FUND=1.0)

    with pytest.raises(ValueError, match="never changes"):
        analyse(price_loader=loader)


def test_a_single_out_of_sample_week_raises_a_clear_error():
    with pytest.raises(ValueError, match="1 week of out-of-sample returns"):
        run_analysis(
            "FUND",
            "2010-01-01",
            "2010-07-02",  # the first trade is on 1 July
            replication=CONFIG,
            asset_classes=SMALL,
            price_loader=fake_prices,
            factor_loader=fake_factors,
            info_loader=fake_info,
        )


def test_a_fund_without_prices_in_the_range_raises():
    def loader(tickers, start, end):
        return fake_prices(tickers, start, end).assign(FUND=np.nan)

    with pytest.raises(ValueError, match="No price data for FUND"):
        analyse(price_loader=loader)


def test_usd_fund_listed_abroad_is_fitted_weekly():
    def info(ticker):
        london = ticker == "FUND.L"
        return {**fake_info(ticker), "timezone": "Europe/London" if london else "America/New_York"}

    a = analyse("FUND.L", info_loader=info)
    assert a.currency == "USD"
    assert a.replication.config.frequency == "weekly"
    assert any("outside US trading hours" in note for note in a.notes)


def test_short_factor_history_leaves_out_only_the_factor_view():
    def factors(region, frequency):
        full = fake_factors(region, frequency)
        return full if frequency == "daily" else full.iloc[-12:]

    a = analyse(factor_loader=factors)
    assert a.attribution is None
    assert a.rolling_betas.empty
    assert any("factor view" in note for note in a.notes)
    assert a.tracking["observations"] > 52  # the clone itself is complete


def test_region_ignores_a_sliver_of_equity():
    assert _region_for({"Bonds": 0.95, "International equity": 0.003, "US equity": 0.002}) == "US"
    assert _region_for({"International equity": 0.9, "US equity": 0.1}) == "Developed ex US"


@pytest.mark.parametrize("weights", [{"AAA": -1, "BBB": 2}, {"AAA": 0}])
def test_invalid_portfolio_weights_raise(weights):
    with pytest.raises(ValueError, match="non-negative"):
        analyse(weights)


def test_a_fund_priced_in_europe_is_pointed_to_the_ucits_etfs():
    a = analyse("FUND.DE")  # fake_info quotes .DE symbols in EUR, without a time zone
    assert any("priced in European hours" in note for note in a.notes)


def test_ucits_etfs_for_a_us_fund_come_with_a_warning_about_timing():
    ucits = [etfs.asset_classes("UCITS")[0], "EUR bonds"]
    a = analyse(asset_classes=ucits, etf_set="UCITS")
    assert any("timing noise" in note for note in a.notes)
    assert any("converted to USD" in note for note in a.notes)
    assert all(ticker.endswith(".DE") for ticker in a.replication.weights.columns)
    held = a.allocation()
    held = held[held["ETF"] != "Cash"]
    assert held["ISIN"].str.len().eq(12).all()  # UCITS ETFs are bought by ISIN


def test_a_clone_of_us_listed_etfs_has_no_isin_column():
    assert "ISIN" not in analyse().allocation().columns
