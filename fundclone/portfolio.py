"""Custom portfolios: parse "VTI 60, VXUS 30, BND 10" and turn holdings into one return series."""

from __future__ import annotations

import math
import re
from collections.abc import Mapping

import pandas as pd

from fundclone.data import daily_returns

MAX_LENGTH = 2000  # characters
# A ticker holds at least one letter, so that "VTI 60 40" is not read as VTI 6 and "0" 40,
# and may start with ^ for an index such as ^GSPC.
_TICKER = r"\^?(?=[0-9.\-=^]*[A-Za-z])[A-Za-z0-9][A-Za-z0-9.\-=^]*"
_GAP = r"(?:\s*:\s*|\s+)"  # between a ticker and its weight
_WEIGHT = r"\d+(?:\.\d+)?(?:\s*%)?"
_ENTRY = re.compile(rf"({_TICKER}){_GAP}(\d+(?:\.\d+)?)(?:\s*%)?")
# Every space has exactly one place in this pattern, so a line that does not match is
# rejected in linear time.
_ENTRIES = re.compile(rf"{_TICKER}{_GAP}{_WEIGHT}(?:\s+{_TICKER}{_GAP}{_WEIGHT})*")


def parse_portfolio(text: str) -> dict[str, float]:
    """Weights by ticker from entries like "VTI 60", "VTI: 60" or "VTI 60%".

    Entries are separated by commas, semicolons, line breaks or just spaces ("VTI 60 BND
    40"). Repeated tickers are added up, and the weights are scaled to sum to one.
    """
    if len(text) > MAX_LENGTH:
        raise ValueError(f"A portfolio can have at most {MAX_LENGTH:,} characters.")
    weights: dict[str, float] = {}
    for entry in filter(str.strip, re.split(r"[,;\n]+", text)):
        if not _ENTRIES.fullmatch(entry.strip()):
            raise ValueError(f"Cannot read {entry.strip()!r}; write entries like 'VTI 60'.")
        for match in _ENTRY.finditer(entry):
            ticker = match.group(1).upper()
            weights[ticker] = weights.get(ticker, 0.0) + float(match.group(2))
    total = sum(weights.values())
    if total <= 0:
        raise ValueError("Enter at least one holding with a positive weight.")
    return {ticker: weight / total for ticker, weight in weights.items()}


def portfolio_returns(prices: pd.DataFrame, weights: Mapping[str, float]) -> pd.Series:
    """Daily returns of a constant-mix portfolio, rebalanced to `weights` every day.

    The series starts once every holding has a price.
    """
    missing = [ticker for ticker in weights if ticker not in prices]
    if missing:
        raise ValueError(f"No price data for {', '.join(missing)}.")
    returns = daily_returns(prices[list(weights)]).dropna()
    return (returns @ pd.Series(weights)).rename("portfolio")


def whole_shares(
    weights: Mapping[str, float], prices: Mapping[str, float], amount: float
) -> dict[str, int]:
    """Whole shares per ticker whose values come as close to `weights` of `amount` as the
    amount allows.

    Each ticker first gets the shares its weight affords, rounded down; then, while the
    cash lasts, one more share goes wherever it narrows the gap to its target most.
    Rounding everything down instead would leave small positions empty. Tickers without a
    positive price get no shares.
    """
    target = {ticker: amount * weight for ticker, weight in weights.items()}
    price = {ticker: float(prices.get(ticker, float("nan"))) for ticker in weights}
    usable = [ticker for ticker, p in price.items() if p > 0]
    shares = dict.fromkeys(weights, 0)
    for ticker in usable:
        shares[ticker] = math.floor(target[ticker] / price[ticker])
    cash = amount - sum(shares[ticker] * price[ticker] for ticker in usable)
    while True:
        gains = {
            t: abs(target[t] - shares[t] * price[t]) - abs(target[t] - (shares[t] + 1) * price[t])
            for t in usable
            if price[t] <= cash
        }
        best = max(gains, key=gains.get, default=None)
        if best is None or gains[best] <= 0:
            return shares
        shares[best] += 1
        cash -= price[best]


def format_portfolio(weights: Mapping[str, float]) -> str:
    """Inverse of parse_portfolio, with weights in percent."""
    return ", ".join(f"{ticker} {100 * weight:g}" for ticker, weight in weights.items())
