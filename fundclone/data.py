"""Data access: Yahoo Finance prices and fund facts, and the Kenneth French data library.

Downloads are cached on disk (``~/.cache/fundclone`` or ``$FUNDCLONE_CACHE``) and reused
until they are stale. If a refresh fails, the stale copy is used rather than failing.
"""

from __future__ import annotations

import contextlib
import io
import json
import os
import re
import time
import zipfile
from collections.abc import Callable, Iterable
from pathlib import Path
from typing import TypeVar

import numpy as np
import pandas as pd
import requests
import yfinance as yf

FRENCH_BASE_URL = "https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/ftp"
CACHE_DIR = Path(os.environ.get("FUNDCLONE_CACHE", Path.home() / ".cache" / "fundclone"))
PRICE_MAX_AGE = 12 * 3600  # seconds
FRENCH_MAX_AGE = 24 * 3600
INFO_MAX_AGE = 7 * 24 * 3600

FF6 = ["Mkt-RF", "SMB", "HML", "RMW", "CMA", "MOM"]

_INTERNATIONAL = {
    "Developed": "Developed",
    "Developed ex US": "Developed_ex_US",
    "Europe": "Europe",
}

# (region, frequency) -> (five-factor file, momentum file), without the .zip suffix
FRENCH_FILES: dict[tuple[str, str], tuple[str, str]] = {
    ("US", "monthly"): ("F-F_Research_Data_5_Factors_2x3_CSV", "F-F_Momentum_Factor_CSV"),
    ("US", "daily"): ("F-F_Research_Data_5_Factors_2x3_daily_CSV", "F-F_Momentum_Factor_daily_CSV"),
    **{
        (region, "monthly"): (f"{stem}_5_Factors_CSV", f"{stem}_Mom_Factor_CSV")
        for region, stem in _INTERNATIONAL.items()
    },
    **{
        (region, "daily"): (f"{stem}_5_Factors_Daily_CSV", f"{stem}_Mom_Factor_Daily_CSV")
        for region, stem in _INTERNATIONAL.items()
    },
}

REGIONS = ["US", *_INTERNATIONAL]

# Data errors: a one-day move beyond ERROR_FLOOR in a series whose typical daily move is
# at most ERROR_FLOOR / ERROR_SIGMAS. In more volatile series, such as single stocks,
# crypto, volatility or leveraged products, errors cannot be told from real moves.
ERROR_FLOOR = 0.15
ERROR_SIGMAS = 8.0
JUMP_FLOOR = 0.45  # unreversed moves this large are reported, or undone if they fit a split
SPLIT_FACTORS = (2, 3, 4, 5, 8, 10, 15, 20, 25, 30, 40, 50, 100)

_DATE_KEY = re.compile(r"\d{6}|\d{8}")
_MISSING_VALUES = [-99.99, -999.0]
_MINOR_UNITS = {"GBp": "GBP", "GBX": "GBP", "ZAc": "ZAR", "ILA": "ILS"}
_ROBUST_SIGMA = 1.4826  # median absolute deviation to standard deviation, for normal data

T = TypeVar("T")


def _cache_file(kind: str, key: str, suffix: str) -> Path:
    """The cache file for `key`, such as a ticker typed by a user. Characters outside a
    small safe set become "_", and the resulting path must stay inside the cache folder."""
    base = os.path.normpath(os.path.join(CACHE_DIR, kind))
    name = re.sub(r"[^A-Za-z0-9._=-]", "_", key) + suffix
    path = os.path.normpath(os.path.join(base, name))
    if not path.startswith(base + os.sep):
        raise ValueError(f"Unsafe cache key: {key!r}")
    return Path(path)


def _is_fresh(path: Path, max_age: float) -> bool:
    return path.exists() and time.time() - path.stat().st_mtime < max_age


def _cached(path: Path, max_age: float, read: Callable[[Path], T]) -> T | None:
    """The cached value if the file is recent enough and readable; a damaged file is a miss."""
    if not _is_fresh(path, max_age):
        return None
    try:
        return read(path)
    except (OSError, ValueError):  # also covers pandas parser and JSON decoding errors
        return None


def _write(path: Path, text: str) -> None:
    """Write atomically, so that an interrupted run cannot leave a truncated cache file."""
    temp = path.with_name(f"{path.name}.{os.getpid()}.tmp")
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        temp.write_text(text)
        os.replace(temp, path)
    except OSError:  # a read-only home directory only costs us the cache
        with contextlib.suppress(OSError):
            temp.unlink(missing_ok=True)


def parse_french_csv(text: str) -> pd.DataFrame:
    """Parse the first table of a Kenneth French CSV file into decimal returns.

    The files open with free-text notes, followed by a header row and data rows keyed
    by YYYYMM (monthly) or YYYYMMDD (daily). Monthly files append a table of annual
    values, which is ignored. Values are converted from percent, the missing-value
    markers become NaN, and monthly rows are stamped at month end.
    """
    lines = text.splitlines()
    keys = [line.split(",", 1)[0].strip() for line in lines]
    start = next((i for i, key in enumerate(keys) if _DATE_KEY.fullmatch(key)), None)
    if start is None:
        raise ValueError("No data rows found in French data file.")
    key_length = len(keys[start])
    stop = start
    while stop < len(lines) and len(keys[stop]) == key_length and _DATE_KEY.fullmatch(keys[stop]):
        stop += 1

    header = next((lines[i] for i in range(start - 1, -1, -1) if lines[i].strip()), "")
    columns = [name.strip() for name in header.split(",")[1:]]
    rows = [[field.strip() for field in line.split(",")[1:]] for line in lines[start:stop]]
    if not columns or any(len(row) != len(columns) for row in rows):
        raise ValueError("Unexpected column layout in French data file.")

    values = pd.DataFrame(rows, columns=columns).apply(pd.to_numeric, errors="coerce")
    values = values.mask(values.isin(_MISSING_VALUES)) / 100.0
    if key_length == 8:
        index = pd.to_datetime(keys[start:stop], format="%Y%m%d")
    else:
        index = pd.to_datetime(keys[start:stop], format="%Y%m") + pd.offsets.MonthEnd(0)
    values.index = pd.DatetimeIndex(index, name="date")
    return values


def _read_french(path: Path) -> str:
    text = path.read_text()
    parse_french_csv(text)  # raises ValueError for a damaged file
    return text


def download_french_file(name: str, timeout: float = 60.0) -> str:
    """Text of one zipped CSV from the French data library, cached for a day."""
    path = _cache_file("french", name, ".csv")
    cached = _cached(path, FRENCH_MAX_AGE, _read_french)
    if cached is not None:
        return cached
    try:
        response = requests.get(f"{FRENCH_BASE_URL}/{name}.zip", timeout=timeout)
        response.raise_for_status()
    except requests.RequestException:
        stale = _cached(path, float("inf"), _read_french)
        if stale is not None:
            return stale
        raise
    with zipfile.ZipFile(io.BytesIO(response.content)) as archive:
        text = archive.read(archive.namelist()[0]).decode("latin-1")
    _write(path, text)
    return text


def load_french_factors(region: str = "US", frequency: str = "monthly") -> pd.DataFrame:
    """Fama-French five factors, momentum and the one-month T-bill rate.

    Returns decimal returns with columns Mkt-RF, SMB, HML, RMW, CMA, MOM and RF.
    International factors are denominated in USD.
    """
    try:
        five_name, momentum_name = FRENCH_FILES[(region, frequency)]
    except KeyError:
        raise ValueError(
            f"No French factor data for region {region!r} at {frequency!r} frequency."
        ) from None
    five = parse_french_csv(download_french_file(five_name))
    momentum = parse_french_csv(download_french_file(momentum_name)).set_axis(["MOM"], axis=1)
    return five.join(momentum, how="inner")[[*FF6, "RF"]].dropna()


_RETRIES = 5  # tickers retried one by one after a batch download leaves them out


def fetch_prices(tickers: Iterable[str], start: str, end: str) -> pd.DataFrame:
    """Split- and dividend-adjusted daily closes from Yahoo Finance, one column per ticker.

    `end` is exclusive. Full histories are cached per ticker for 12 hours. Tickers
    without data are left out. yfinance's shared SQLite cache sometimes fails under
    concurrent access, so the first few tickers that come back empty are retried one by
    one.
    """
    tickers = list(dict.fromkeys(tickers))
    closes: dict[str, pd.Series] = {}
    stale: list[str] = []
    for ticker in tickers:
        cached = _cached(_cache_file("prices", ticker, ".csv"), PRICE_MAX_AGE, _read_prices)
        if cached is None:
            stale.append(ticker)
        else:
            closes[ticker] = cached
    if stale:
        downloaded = _download_closes(stale)
        for ticker in [t for t in stale if t not in downloaded][:_RETRIES]:
            downloaded.update(_download_closes([ticker]))
        for ticker in stale:
            path = _cache_file("prices", ticker, ".csv")
            if ticker in downloaded:
                closes[ticker] = downloaded[ticker]
                _write(path, downloaded[ticker].rename("close").to_csv())
            else:
                old = _cached(path, float("inf"), _read_prices)
                if old is not None:
                    closes[ticker] = old
    if not closes:
        return pd.DataFrame()
    prices = pd.concat(closes, axis=1, sort=True)
    prices = prices[(prices.index >= pd.Timestamp(start)) & (prices.index < pd.Timestamp(end))]
    return prices[[t for t in tickers if t in prices]].dropna(how="all")


def _read_prices(path: Path) -> pd.Series:
    series = pd.read_csv(path, index_col=0, parse_dates=True).iloc[:, 0].dropna()
    if series.empty or not isinstance(series.index, pd.DatetimeIndex):
        raise ValueError(f"Damaged price cache {path}")
    return series.astype(float)


def _download_closes(tickers: list[str]) -> dict[str, pd.Series]:
    try:
        raw = yf.download(tickers, period="max", auto_adjust=True, progress=False, threads=False)
    except Exception:  # yfinance raises assorted errors for bad symbols and network trouble
        return {}
    if raw is None or raw.empty:
        return {}
    close = raw["Close"]
    if isinstance(close, pd.Series):
        close = close.to_frame(tickers[0])
    index = pd.DatetimeIndex(close.index)
    close = close.set_axis(index.tz_localize(None) if index.tz is not None else index)
    return {t: close[t].dropna() for t in close.columns if close[t].notna().any()}


def fetch_info(ticker: str) -> dict:
    """Name, currency, exchange time zone, quote type and net expense ratio (decimal) of a
    Yahoo Finance symbol.

    Values Yahoo does not report are None. Cached for a week.
    """
    path = _cache_file("info", ticker, ".json")
    cached = _cached(path, INFO_MAX_AGE, lambda p: json.loads(p.read_text()))
    if isinstance(cached, dict):
        return cached
    try:
        raw = yf.Ticker(ticker).info or {}
    except Exception:  # unknown symbols and rate limits surface as assorted errors
        raw = {}
    ratio = raw.get("netExpenseRatio")
    info = {
        "name": raw.get("longName") or raw.get("shortName"),
        "currency": raw.get("currency"),
        "timezone": raw.get("exchangeTimezoneName"),
        "quote_type": raw.get("quoteType"),
        "expense_ratio": float(ratio) / 100 if ratio is not None else None,
    }
    for key in ("currency", "timezone"):
        if info[key] is None:
            try:
                info[key] = yf.Ticker(ticker).fast_info[key]
            except Exception:  # leave it unknown
                pass
    if raw:
        _write(path, json.dumps(info))
    return info


def fx_ticker(currency: str) -> str | None:
    """Yahoo symbol quoting the USD price of one unit of `currency`; None for USD.

    Minor units (GBp, ZAc, ILA) map to their major currency: the constant factor of
    100 cancels in returns.
    """
    code = _MINOR_UNITS.get(currency, currency.upper())
    return None if code == "USD" else f"{code}USD=X"


def to_usd(prices: pd.Series, fx_rates: pd.Series) -> pd.Series:
    """Convert local-currency prices with USD-per-unit rates, using the last known rate."""
    rates = fx_rates.dropna()
    rates = rates.reindex(rates.index.union(prices.index)).ffill().reindex(prices.index)
    return (prices * rates).dropna()


def compounded_rate(rates: pd.Series, dates: pd.DatetimeIndex) -> pd.Series:
    """Interest earned from each of `dates` to the next at daily `rates`, labelled by the
    later date.

    The rates are per business day. A date that follows a gap, such as a holiday or a
    stale price merged with the next day, earns the interest of every business day since
    the previous date. Beyond the last known rate, that rate is carried forward. The first
    date gets NaN.
    """
    rates = rates.dropna()
    if len(dates) and dates[-1] > rates.index[-1]:
        future = pd.bdate_range(rates.index[-1] + pd.offsets.BDay(1), dates[-1])
        rates = pd.concat([rates, pd.Series(rates.iloc[-1], index=future)])
    growth = (1 + rates).cumprod()
    growth = growth.reindex(growth.index.union(dates)).ffill().reindex(dates)
    return growth / growth.shift(1) - 1


def drop_stale_prices(
    prices: pd.Series, market_returns: pd.DataFrame, threshold: float = 0.004, window: int = 252
) -> pd.Series:
    """Remove prices that repeat the previous day's on days when the fund should have moved.

    Yahoo Finance sometimes repeats a mutual fund's previous price and catches up a day
    later. Dropping such a day merges it with the next one, as if the fund had not traded,
    instead of recording a false zero return followed by a double move. `market_returns`
    holds daily returns of reference ETFs on the fund's calendar. The move to expect from
    the fund on a day is its beta to their median return, estimated over the previous
    `window` days, times that day's median return; an unchanged price counts as stale when
    that expected move exceeds `threshold`. So the unchanged price of a bond fund on a day
    when only stocks moved is kept.
    """
    fund = prices / prices.shift(1) - 1
    market = market_returns.median(axis=1).reindex(prices.index)
    past = pd.DataFrame({"fund": fund, "market": market}).shift(1)
    covariance = past["fund"].rolling(window, min_periods=63).cov(past["market"])
    beta = covariance / past["market"].rolling(window, min_periods=63).var()
    stale = (fund.abs() < 1e-12) & ((beta * market).abs() > threshold)
    return prices[~stale]


def _typical_move(prices: pd.Series) -> float:
    """Robust estimate of the standard deviation of daily returns."""
    moves = (prices / prices.shift(1) - 1).abs().dropna()
    return _ROBUST_SIGMA * float(moves.median()) if len(moves) else 0.0


def _too_volatile(prices: pd.Series) -> bool:
    """Whether a data error could not be told from a genuine move in this series."""
    return ERROR_SIGMAS * _typical_move(prices) > ERROR_FLOOR


def _calm(prices: pd.Series, market_returns: pd.DataFrame, limit: float) -> np.ndarray:
    """Days on which the median reference ETF moved less than a quarter of `limit`."""
    market = market_returns.abs().median(axis=1).reindex(prices.index).fillna(0.0)
    return (market < limit / 4).to_numpy()


def drop_price_errors(
    prices: pd.Series, market_returns: pd.DataFrame, days: int = 5, tolerance: float = 0.03
) -> pd.Series:
    """Remove prices that jump away and come back within a few days while the market is calm.

    A jump is a move of more than ERROR_FLOOR on a day when the median reference ETF moved
    less than a quarter as much. If the price returns to within `tolerance` of its level
    before the jump in at most `days` days, the prices in between are data errors, such as
    a misplaced decimal point, and are dropped. Series too volatile for an error to stand
    out are returned unchanged.
    """
    if _too_volatile(prices):
        return prices
    values = prices.to_numpy(dtype=float)
    calm = _calm(prices, market_returns, ERROR_FLOOR)
    bad = np.zeros(len(values), dtype=bool)
    good, i = 0, 1  # the last good price, and the price being checked
    while i < len(values):
        back = None
        if abs(values[i] / values[good] - 1) > ERROR_FLOOR and calm[i]:
            back = next(
                (
                    k
                    for k in range(i + 1, min(i + 1 + days, len(values)))
                    if abs(values[k] / values[good] - 1) <= tolerance
                ),
                None,
            )
        if back is None:
            good, i = i, i + 1
        else:
            bad[i:back] = True
            good, i = back, back + 1
    return prices[~bad]


def price_jumps(prices: pd.Series, market_returns: pd.DataFrame) -> pd.Series:
    """Daily moves beyond JUMP_FLOOR on a calm market day, in a series calm enough for them
    to stand out. They usually come from a data error such as an unadjusted split."""
    if _too_volatile(prices):
        return pd.Series(dtype=float)
    moves = prices / prices.shift(1) - 1
    return moves[(moves.abs() > JUMP_FLOOR).to_numpy() & _calm(prices, market_returns, JUMP_FLOOR)]


def split_factor(ratio: float, tolerance: float = 0.03) -> float | None:
    """The split ratio a one-day price ratio matches within `tolerance`: 1/k after a
    k-for-1 split, k after a 1-for-k reverse split; None if it matches none."""
    for k in SPLIT_FACTORS:
        for factor in (1 / k, float(k)):
            if abs(ratio / factor - 1) <= tolerance:
                return factor
    return None


def adjust_splits(
    prices: pd.Series, market_returns: pd.DataFrame
) -> tuple[pd.Series, list[tuple[pd.Timestamp, float, float]]]:
    """Undo unadjusted splits: every jump that price_jumps reports and whose size matches a
    split ratio rescales the earlier prices by that ratio. Returns the prices and, for each
    split found, its date, the split ratio and the move observed that day."""
    splits = []
    for date, move in price_jumps(prices, market_returns).items():
        factor = split_factor(1 + move)
        if factor is not None:
            prices = prices.where(prices.index >= date, prices * factor)
            splits.append((date, factor, float(move)))
    return prices, splits


def daily_returns(prices: pd.DataFrame | pd.Series) -> pd.DataFrame | pd.Series:
    """Simple daily returns. Gaps inside a series are bridged so that no move is lost."""
    filled = prices.ffill().where(prices.bfill().notna())
    return (filled / filled.shift(1) - 1).iloc[1:]


def weekly_returns(returns: pd.DataFrame | pd.Series) -> pd.DataFrame | pd.Series:
    """Compound daily returns into weeks labelled by their Friday; empty weeks are dropped."""
    return ((1 + returns).resample("W-FRI").prod(min_count=1) - 1).dropna(how="all")


def monthly_returns(prices: pd.DataFrame | pd.Series) -> pd.DataFrame | pd.Series:
    """Returns between consecutive month-end prices.

    The first month has no prior month-end and is dropped; so is the last month
    unless the prices reach within three calendar days of its end.
    """
    prices = prices.dropna(how="all")
    month_end = prices.resample("ME").last()
    returns = (month_end / month_end.shift(1) - 1).iloc[1:]
    last = prices.index[-1]
    if (last + pd.offsets.MonthEnd(0) - last).days > 3:
        returns = returns.iloc[:-1]
    return returns
