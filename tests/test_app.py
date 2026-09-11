"""The web app, run headless on synthetic data."""

import datetime as dt
from pathlib import Path

import pytest

pytest.importorskip("streamlit")

import streamlit as st  # noqa: E402
from fakes import fake_factors, fake_info, fake_prices  # noqa: E402
from streamlit.testing.v1 import AppTest  # noqa: E402

from factorlens import data  # noqa: E402

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


def test_a_clone_in_cash_renders(app, monkeypatch):
    monkeypatch.setattr(data, "fetch_prices", inverse_prices)
    app.query_params["ticker"] = "FUND"
    app.run()
    assert not app.exception
    assert any("only T-bills" in element.value for element in app.caption)
