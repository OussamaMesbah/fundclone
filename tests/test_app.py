"""The web app, run headless on synthetic data."""

import datetime as dt
from pathlib import Path

import pandas as pd
import pytest

pytest.importorskip("streamlit")

import streamlit as st  # noqa: E402
from fakes import fake_factors, fake_info, fake_prices  # noqa: E402
from streamlit.testing.v1 import AppTest  # noqa: E402

from fundclone import data, etfs  # noqa: E402

APP = str(Path(__file__).parents[1] / "streamlit_app.py")


def inverse_prices(tickers, start, end):
    """Like fake_prices, but FUND moves against every ETF, so a long-only clone holds cash."""
    prices = fake_prices(tickers, start, end)
    market = prices.drop(columns="FUND").pct_change().mean(axis=1).fillna(0.0)
    return prices.assign(FUND=100 * (1 - market).cumprod())


@pytest.fixture
def app(monkeypatch):
    monkeypatch.setattr(data, "fetch_prices", fake_prices)
    monkeypatch.setattr(data, "load_french_factors", fake_factors)
    monkeypatch.setattr(data, "fetch_info", fake_info)
    st.cache_data.clear()
    st.cache_resource.clear()
    return AppTest.from_file(APP, default_timeout=180)


def widget(elements, label):
    return next(element for element in elements if element.label == label)


def test_the_default_page_builds_a_clone(app):
    app.run()
    assert not app.exception
    assert any("A clone of" in element.value for element in app.markdown)


def test_a_link_restores_the_settings(app):
    app.query_params.update(ticker="FUND", start="2011-01-03", etfs="5", window="252")
    app.run()
    assert not app.exception
    assert widget(app.date_input, "Start").value == dt.date(2011, 1, 3)
    assert widget(app.selectbox, "ETFs in the clone").value == "5"
    assert widget(app.slider, "Estimation window, trading days").value == 252


def test_a_link_value_the_form_cannot_show_is_ignored(app):
    app.query_params.update(ticker="FUND", etfs="4")
    app.run()
    assert not app.exception
    assert widget(app.selectbox, "ETFs in the clone").value == "Automatic"


def test_the_app_falls_back_to_a_local_price_snapshot(app, monkeypatch, tmp_path):
    snapshot = tmp_path / "prices.parquet"
    tickers = ["AGTHX", *etfs.tickers(), "IEF", "LQD"]
    fake_prices(tickers, "2000-01-01", "2030-01-01").to_parquet(snapshot)
    monkeypatch.setenv("FUNDCLONE_SNAPSHOT", str(snapshot))
    monkeypatch.setattr(data, "fetch_prices", lambda tickers, start, end: pd.DataFrame())
    app.query_params["ticker"] = "AGTHX"
    app.run()
    assert not app.exception
    assert any("snapshot of" in element.value for element in app.caption)


def test_a_clone_in_cash_renders(app, monkeypatch):
    monkeypatch.setattr(data, "fetch_prices", inverse_prices)
    app.query_params["ticker"] = "FUND"
    app.run()
    assert not app.exception
    assert any("only T-bills" in element.value for element in app.caption)


def test_a_link_cannot_put_markdown_on_the_page(app):
    app.query_params["portfolio"] = "[Sign in](https://evil.example/login) 60"
    app.run()
    assert not app.exception
    shown = [element.value.replace("\\", "") for element in app.error]
    assert shown and all("https://" not in text for text in shown)


def test_a_link_with_a_malformed_ticker_is_ignored(app):
    app.query_params["ticker"] = "[Sign in](https://evil.example/login)"
    app.run()
    assert not app.exception
    assert not any("evil.example" in str(element.value) for element in app.markdown)


def test_factsheet_details_are_shown_as_plain_text(app, monkeypatch):
    from fundclone import factsheet

    hostile = {
        "fund_name": "[Sign in](https://evil.example) www.evil.example",
        "isins": [],
        "ticker_candidates": ["EVIL"],
    }
    monkeypatch.setattr(factsheet, "parse_factsheet_safely", lambda pdf: hostile)
    app.run()
    app.file_uploader[0].set_value(("factsheet.pdf", b"%PDF-1.4", "application/pdf")).run()
    assert not app.exception
    shown = [m.value.replace("\\", "") for m in app.markdown if "evil" in m.value]
    assert shown and all("https://" not in text and "www." not in text for text in shown)


def test_switching_shows_the_tax_and_how_long_it_takes_to_earn_it_back(app):
    app.query_params["ticker"] = "FUND"  # the synthetic fund with an expense ratio
    app.run()
    widget(app.number_input, "Unrealised gain, % of the amount").set_value(40.0).run()
    assert not app.exception
    captions = [element.value for element in app.caption]
    assert any("600 USD in tax" in text for text in captions)
    assert any("years to earn back" in text for text in captions)
    assert any("trades about" in text and "the 35% the fund reports" in text for text in captions)
    assert any("starting with none" in text for text in captions)


def test_the_snapshot_is_used_while_yahoo_limits_every_request(app, monkeypatch, tmp_path):
    snapshot = tmp_path / "prices.parquet"
    tickers = ["AGTHX", *etfs.tickers(), "IEF", "LQD"]
    fake_prices(tickers, "2000-01-01", "2030-01-01").to_parquet(snapshot)
    monkeypatch.setenv("FUNDCLONE_SNAPSHOT", str(snapshot))

    def limited(*args, **kwargs):
        raise data.YahooRateLimitError(["AGTHX"])

    monkeypatch.setattr(data, "fetch_prices", limited)
    monkeypatch.setattr(data, "fetch_info", limited)
    app.query_params["ticker"] = "AGTHX"
    app.run()
    assert not app.exception
    assert any("snapshot of" in element.value for element in app.caption)


def test_a_linked_expense_ratio_the_form_cannot_show_is_ignored(app):
    app.query_params.update(ticker="FUND", ter="9.995")
    app.run()
    assert not app.exception
    assert widget(app.number_input, "Expense ratio, % a year (optional)").value is None


def test_an_expense_ratio_entered_for_one_fund_is_not_used_for_the_next(app):
    app.query_params.update(ticker="FUND", ter="1.5")
    app.run()
    widget(app.text_input, "Ticker").set_value("OTHER")
    next(button for button in app.button if button.label == "Build the clone").click().run()
    assert not app.exception
    assert not any("is the one entered" in element.value for element in app.caption)


def test_an_isin_lookup_during_a_rate_limit_says_so(app, monkeypatch):
    def limited(isin, limit=5):
        raise data.YahooRateLimitError()

    monkeypatch.setattr(data, "yahoo_symbols", limited)
    app.run()
    widget(app.text_input, "ISIN").set_value("de0009848119").run()
    assert not app.exception
    assert any("limiting requests" in element.value for element in app.caption)


def test_a_link_can_set_the_expense_ratio(app):
    app.query_params.update(ticker="FUND", ter="1.5")
    app.run()
    assert not app.exception
    assert widget(app.number_input, "Expense ratio, % a year (optional)").value == 1.5
    shown = [element.value.replace("\\", "") for element in app.markdown]
    assert any("the fund charges 1.50%" in text for text in shown)


def test_a_front_end_load_already_paid_does_not_shorten_the_payback(app):
    app.query_params["ticker"] = "FUND"
    app.run()
    widget(app.number_input, "Unrealised gain, % of the amount").set_value(40.0).run()
    payback = next(element.value for element in app.caption if "to earn back" in element.value)
    widget(app.number_input, "Front-end load on new money, %").set_value(5.75).run()
    assert not app.exception
    captions = [element.value for element in app.caption]
    assert payback in captions
    assert any("New money" in text and "0.59% a year" in text for text in captions)


def test_a_deferred_sales_charge_is_part_of_the_cost_of_selling(app):
    app.query_params["ticker"] = "FUND"
    app.run()
    widget(app.number_input, "Deferred sales charge if you sell now, %").set_value(1.0).run()
    assert not app.exception
    captions = [element.value for element in app.caption]
    assert any("100 USD in deferred sales charge" in text for text in captions)


def test_an_isin_shows_yahoo_symbols_to_choose_from(app, monkeypatch):
    found = [
        {
            "symbol": "0P00000ABC.F",
            "name": "DWS Top Dividende",
            "type": "MUTUALFUND",
            "exchange": "FRA",
            "days": 2000,
            "prices_from": "2018-01-02",
        },
        {
            "symbol": "HJUA.F",
            "name": "DWS Top Dividende",
            "type": "ETF",
            "exchange": "FRA",
            "days": 0,
            "prices_from": None,
        },
    ]
    monkeypatch.setattr(data, "yahoo_symbols", lambda isin, limit=5: found)
    app.run()
    widget(app.text_input, "ISIN").set_value("de0009848119").run()
    assert not app.exception
    shown = " ".join(element.value for element in app.markdown)
    assert "HJUA.F" in shown and "no prices" in shown
    assert "prices since 2018-01-02" in shown
    assert any("share class" in element.value for element in app.caption)


def test_a_link_can_choose_the_ucits_etfs(app):
    app.query_params["ticker"] = "FUND"
    app.query_params["set"] = "UCITS"
    app.run()
    assert not app.exception
    assert widget(app.radio, "ETFs").value == "UCITS"
    blocks = widget(app.multiselect, "Building blocks")
    assert "World equity" in blocks.value and "US equity" not in blocks.value
    assert any("timing noise" in element.value for element in app.caption)


def test_the_clone_tab_can_list_ucits_twins(app):
    app.query_params["ticker"] = "FUND"
    app.run()
    widget(app.toggle, "UCITS twins for investors in the EU").set_value(True).run()
    assert not app.exception
    assert any("not tested here" in element.value for element in app.caption)
