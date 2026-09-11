"""Synthetic prices, factors and fund facts for offline end-to-end tests."""

import numpy as np
import pandas as pd

from fundclone.analysis import run_analysis
from fundclone.data import FF6
from fundclone.replication import ReplicationConfig

DATES = pd.bdate_range("2010-01-01", "2014-12-31")
CONFIG = ReplicationConfig(window=126)
SMALL = ["US equity", "Bonds"]


def fake_prices(tickers, start, end):
    rng = np.random.default_rng(42)
    market = rng.normal(0.0004, 0.01, len(DATES))
    prices = pd.DataFrame(
        {
            ticker: 100
            * np.cumprod(1 + (0.5 + 0.02 * i) * market + rng.normal(0, 0.004, len(DATES)))
            for i, ticker in enumerate(tickers)
        },
        index=DATES,
    )
    return prices[(prices.index >= start) & (prices.index < end)]


def fake_factors(region, frequency):
    rng = np.random.default_rng(7)
    if frequency == "monthly":
        index = pd.date_range("2009-01-31", "2014-12-31", freq="ME")
    else:
        index = DATES
    factors = pd.DataFrame(
        rng.normal(0.004, 0.03, (len(index), len(FF6))), index=index, columns=FF6
    )
    factors["RF"] = 0.001 if frequency == "monthly" else 0.00004
    return factors


def fake_info(ticker):
    return {
        "name": f"{ticker} Fund",
        "currency": "EUR" if ticker.endswith(".DE") else "USD",
        "quote_type": "MUTUALFUND",
        "expense_ratio": 0.0075 if ticker == "FUND" else None,
    }


def analyse(target="FUND", **kwargs):
    kwargs.setdefault("asset_classes", SMALL)
    return run_analysis(
        target,
        "2010-01-01",
        "2014-12-31",
        replication=kwargs.pop("replication", CONFIG),
        price_loader=kwargs.pop("price_loader", fake_prices),
        factor_loader=kwargs.pop("factor_loader", fake_factors),
        info_loader=kwargs.pop("info_loader", fake_info),
        **kwargs,
    )
