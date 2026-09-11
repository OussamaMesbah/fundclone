"""End-to-end analysis: clone a fund or a portfolio with ETFs and explain it with factors."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass, field, replace

import pandas as pd

from fundclone import etfs
from fundclone.attribution import (
    BOND_FACTOR_TICKERS,
    AttributionResult,
    bond_factors,
    factor_regression,
    rolling_betas,
)
from fundclone.data import (
    FF6,
    adjust_splits,
    compounded_rate,
    daily_returns,
    drop_price_errors,
    drop_stale_prices,
    fetch_info,
    fetch_prices,
    fx_ticker,
    load_french_factors,
    monthly_returns,
    price_jumps,
    to_usd,
    weekly_returns,
)
from fundclone.estimators import make_estimator
from fundclone.metrics import TRADING_DAYS, WEEKS_PER_YEAR, benchmark_fit, performance, tracking
from fundclone.portfolio import portfolio_returns
from fundclone.replication import ReplicationConfig, ReplicationResult, walk_forward

PERIODS_PER_YEAR = {"monthly": 12, "daily": TRADING_DAYS}
TRADING_DAYS_PER_MONTH = 21
STALE_RATE_DAYS = 62  # the French library usually lags one to two months; beyond that, say so
PORTFOLIO_LABEL = "Portfolio"
US_TIMEZONES = {"America/New_York"}  # exchanges whose prices are set with the ETFs' closes
# Quote types whose sudden jumps are checked for data errors and unadjusted splits (None:
# unknown). Single stocks, crypto and the like are left alone: their jumps are often real.
FUND_TYPES = {None, "MUTUALFUND", "ETF", "MONEYMARKET"}
MIN_EQUITY_FOR_REGION = 0.2  # below this share of equity the region follows noise: use US


@dataclass
class Analysis:
    """Everything the app and the command line show for one fund or portfolio."""

    label: str  # the ticker, or "Portfolio"
    name: str
    holdings: dict[str, float] | None  # weights of a custom portfolio, None for a fund
    currency: str
    expense_ratio: float | None  # the fund's net expense ratio as reported by Yahoo Finance
    replication: ReplicationResult
    returns: pd.DataFrame  # daily out-of-sample returns: fund, clone, closest, rf
    closest_etf: str  # the single ETF that tracked the fund best over the same weeks
    performance: pd.DataFrame  # one row per series, columns from metrics.performance
    tracking_returns: pd.DataFrame  # weekly fund, clone and closest returns
    tracking: dict[str, float]  # metrics.tracking of the clone, on weekly returns
    closest_tracking: dict[str, float]  # the same for the closest single ETF
    benchmark_fit: dict[str, float]  # beta, R² and tracking error against the closest ETF
    equity_share: float  # share of the clone's invested weight held in equity ETFs
    region: str  # of the factor model
    frequency: str  # of the attribution: "monthly" or "daily"
    bond_factors: bool
    attribution: AttributionResult | None  # None when the history is too short for it
    rolling_window: int  # months
    rolling_betas: pd.DataFrame
    notes: list[str] = field(default_factory=list)

    @property
    def labels(self) -> dict[str, str]:
        return {"fund": self.label, "clone": "ETF clone", "closest": self.closest_etf}

    @property
    def tracking_periods_per_year(self) -> int:
        """Tracking is measured on weekly returns, which daily pricing noise barely touches."""
        return WEEKS_PER_YEAR

    @property
    def current_weights(self) -> pd.Series:
        """The clone's latest target weights, largest first, zero weights left out."""
        latest = self.replication.weights.iloc[-1]
        return latest[latest > 1e-4].sort_values(ascending=False)

    @property
    def clone_expense_ratio(self) -> float:
        return etfs.expense_ratio(self.current_weights.to_dict())

    def allocation(self) -> pd.DataFrame:
        """The current clone: ETF, name, asset class, weight and expense ratio, plus cash."""
        rows = [
            {
                "ETF": ticker,
                "Name": etfs.BY_TICKER[ticker].name,
                "Asset class": etfs.BY_TICKER[ticker].asset_class,
                "Weight": weight,
                "Expense ratio": etfs.BY_TICKER[ticker].expense_ratio,
            }
            for ticker, weight in self.current_weights.items()
        ]
        cash = 1.0 - float(self.current_weights.sum())
        if abs(cash) > 1e-4:
            rows.append(
                {
                    "ETF": "Cash",
                    "Name": "T-bills or a money-market fund",
                    "Asset class": "Cash",
                    "Weight": cash,
                    "Expense ratio": 0.0,
                }
            )
        return pd.DataFrame(rows)


def run_analysis(
    target: str | Mapping[str, float],
    start: str,
    end: str,
    replication: ReplicationConfig | None = None,
    asset_classes: list[str] | None = None,
    frequency: str = "monthly",
    region: str | None = None,
    use_bond_factors: bool | None = None,
    rolling_window: int = 36,
    *,
    price_loader: Callable[..., pd.DataFrame] = fetch_prices,
    factor_loader: Callable[..., pd.DataFrame] = load_french_factors,
    info_loader: Callable[[str], dict] = fetch_info,
) -> Analysis:
    """Clone a fund (a Yahoo Finance ticker) or a portfolio ({ticker: weight}) with ETFs.

    `start` and `end` are inclusive ISO dates. `asset_classes` restricts the ETFs the
    clone may use (see etfs.ASSET_CLASSES). The factor model's `region` and whether it
    includes term and credit factors default to what the clone holds. A replication
    frequency of "auto" becomes weekly when anything is priced outside US trading hours.
    The loaders can be replaced by cached or offline versions with the same signatures; a
    price loader can pass notes for the user on in the returned frame's attrs["notes"].
    """
    config = replication or ReplicationConfig()
    notes: list[str] = []
    if isinstance(target, str):
        label, holdings = target.strip().upper(), None
        members = [label]
    else:
        label = PORTFOLIO_LABEL
        holdings = _normalised(target)
        members = list(holdings)

    infos = {ticker: info_loader(ticker) for ticker in members}
    currencies = {}
    for ticker, info in infos.items():
        if not info.get("currency"):
            notes.append(f"Yahoo Finance reports no currency for {ticker}; prices are read as USD.")
        currencies[ticker] = info.get("currency") or "USD"
    foreign = {ticker: c for ticker, c in currencies.items() if fx_ticker(c)}
    if config.frequency == "auto":
        abroad = [ticker for ticker in members if _priced_abroad(ticker, infos[ticker])]
        config = replace(config, frequency="weekly" if abroad else "daily")
        if abroad:
            notes.append(
                f"{', '.join(abroad)} {'is' if len(abroad) == 1 else 'are'} priced outside US "
                "trading hours, so the clone is fitted on weekly returns."
            )

    universe = etfs.tickers(asset_classes)
    if holdings is None and label in universe:
        universe.remove(label)
        notes.append(f"{label} itself is left out of the ETFs the clone may use.")
    fx = sorted({fx_ticker(c) for c in foreign.values()})
    tickers = [*members, *universe, *BOND_FACTOR_TICKERS, *fx]
    end_exclusive = (pd.Timestamp(end) + pd.Timedelta(days=1)).strftime("%Y-%m-%d")
    prices = price_loader(tickers, start, end_exclusive)
    notes.extend(prices.attrs.get("notes", []))
    universe = [ticker for ticker in universe if ticker in prices]

    missing = [t for t in members if t not in prices or prices[t].dropna().empty]
    if missing:
        raise ValueError(
            f"No price data for {', '.join(missing)} on Yahoo Finance between {start} and "
            f"{end}. Check the ticker; if every ticker fails, Yahoo may be refusing requests "
            "(pip install -U yfinance helps when it has changed its interface)."
        )
    member_prices = {}
    for ticker in members:
        series = prices[ticker].dropna()
        if ticker in foreign:
            rate = fx_ticker(foreign[ticker])
            if rate not in prices:
                raise ValueError(
                    f"{ticker} trades in {foreign[ticker]}, "
                    f"but no {rate} exchange rates were found."
                )
            series = to_usd(series, prices[rate])
        member_prices[ticker] = series
    flat = [t for t, s in member_prices.items() if not ((s / s.shift(1) - 1).abs() > 1e-12).any()]
    if flat:
        raise ValueError(
            f"The price of {', '.join(flat)} on Yahoo Finance never changes (a money-market "
            "fund's price leaves out its income), so there is nothing to clone; a T-bill ETF "
            "such as BIL can stand in for it."
        )
    indices = [t for t in members if t.startswith("^")]
    if indices:
        kind = "is a price index" if len(indices) == 1 else "are price indices"
        notes.append(
            f"{', '.join(indices)} {kind} without dividends, so the gap to the clone includes "
            "the dividend yield."
        )
    if foreign:
        quoted = ", ".join(f"{ticker} ({currency})" for ticker, currency in foreign.items())
        notes.append(f"Returns of {quoted} are converted to USD.")
    if holdings is None:
        fund_like = infos[label].get("quote_type") in FUND_TYPES
        fund_prices = _cleaned(member_prices[label], prices[universe], label, notes, fund_like)
        name = infos[label].get("name") or label
        expense = infos[label].get("expense_ratio")
    else:
        fund_prices = _index(portfolio_returns(pd.DataFrame(member_prices), holdings))
        name, expense = "Custom portfolio", None

    # Every daily series is put on the fund's trading calendar, so that holidays in one
    # market (or stale fund prices dropped above) do not lose another series' returns.
    on_fund_days = prices.ffill().reindex(fund_prices.index)
    replication_result, returns, closest = _replicate(
        fund_prices, on_fund_days, universe, config, factor_loader, notes
    )

    classes = etfs.asset_class_weights(replication_result.weights.mean().to_dict())
    region = region or _region_for(classes)
    if use_bond_factors is None:
        use_bond_factors = classes.get("Bonds", 0.0) > 0.25
    attribution, betas, use_bond_factors = _attribute(
        fund_prices,
        prices,
        on_fund_days,
        region,
        frequency,
        use_bond_factors,
        rolling_window,
        factor_loader,
        notes,
    )

    labels = {"fund": label, "clone": "ETF clone", "closest": closest}
    perf = pd.DataFrame({labels[c]: performance(returns[c], returns["rf"]) for c in labels}).T
    weekly = weekly_returns(returns[["fund", "clone", "closest"]])
    return Analysis(
        label=label,
        name=name,
        holdings=holdings,
        currency=currencies[label] if holdings is None else "USD",
        expense_ratio=expense,
        replication=replication_result,
        returns=returns,
        closest_etf=closest,
        performance=perf,
        tracking_returns=weekly,
        tracking=tracking(weekly["fund"], weekly["clone"], WEEKS_PER_YEAR),
        closest_tracking=tracking(weekly["fund"], weekly["closest"], WEEKS_PER_YEAR),
        benchmark_fit=benchmark_fit(weekly["fund"], weekly["closest"], WEEKS_PER_YEAR),
        equity_share=_equity_share(classes),
        region=region,
        frequency=frequency,
        bond_factors=use_bond_factors,
        attribution=attribution,
        rolling_window=rolling_window,
        rolling_betas=betas,
        notes=notes,
    )


def _priced_abroad(ticker: str, info: Mapping) -> bool:
    """Whether the price is set outside US trading hours: quoted in another currency, listed
    on a non-US exchange or, when Yahoo reports no time zone, carrying a Yahoo suffix for a
    foreign exchange such as .L or .DE."""
    if fx_ticker(info.get("currency") or "USD"):
        return True
    timezone = info.get("timezone")
    if timezone:
        return timezone not in US_TIMEZONES
    return "." in ticker


def _cleaned(
    fund_prices: pd.Series,
    etf_prices: pd.DataFrame,
    label: str,
    notes: list[str],
    fund_like: bool = True,
) -> pd.Series:
    """The fund's prices without stale days and, for funds and ETFs, without one-off data
    errors and unadjusted splits, with a note on each change."""
    market = daily_returns(etf_prices.ffill().reindex(fund_prices.index))
    checked = drop_price_errors(fund_prices, market) if fund_like else fund_prices
    errors = fund_prices.index.difference(checked.index)
    if len(errors):
        verdict = (
            "it looks like a data error and is"
            if len(errors) == 1
            else "they look like data errors and are"
        )
        notes.append(
            f"{label} has {_count(len(errors), 'price')} that jumped by more than 15% and came "
            f"back within days without a matching market move; {verdict} left out "
            f"({_dates(errors)})."
        )
    cleaned = drop_stale_prices(checked, market)
    stale = len(checked) - len(cleaned)
    if stale:
        notes.append(
            f"On {_count(stale, 'day')} {label}'s price did not change although the market "
            "moved enough to move it; each such day is merged with the following day."
        )
    if not fund_like:
        return cleaned
    cleaned, splits = adjust_splits(cleaned, market)
    for date, factor, move in splits:
        kind = (
            f"{round(1 / factor)}-for-1 split"
            if factor < 1
            else f"1-for-{round(factor)} reverse split"
        )
        notes.append(
            f"{label}'s price moved {move:+.0%} on {date:%Y-%m-%d}, close to what an unadjusted "
            f"{kind} would do; earlier prices are adjusted for it."
        )
    for date, move in price_jumps(cleaned, market).head(3).items():
        notes.append(
            f"{label}'s price moved {move:+.0%} on {date:%Y-%m-%d} without a matching market "
            "move, which may be a data error; it is left in the figures."
        )
    return cleaned


def _count(n: int, noun: str) -> str:
    return f"{n} {noun}{'' if n == 1 else 's'}"


def _dates(index: pd.DatetimeIndex) -> str:
    shown = ", ".join(f"{date:%Y-%m-%d}" for date in index[:3])
    return shown + (" and others" if len(index) > 3 else "")


def _index(returns: pd.Series) -> pd.Series:
    """A price index of 100 on the day before the first return."""
    start = returns.index[0] - pd.offsets.BDay(1)
    return pd.concat([pd.Series({start: 100.0}), 100 * (1 + returns).cumprod()])


def _normalised(weights: Mapping[str, float]) -> dict[str, float]:
    """Portfolio weights by upper-case ticker, scaled to sum to one."""
    cleaned: dict[str, float] = {}
    for ticker, weight in weights.items():
        key = ticker.strip().upper()
        cleaned[key] = cleaned.get(key, 0.0) + float(weight)
    total = sum(cleaned.values())
    if total <= 0 or min(cleaned.values()) < 0:
        raise ValueError("Portfolio weights must be non-negative and add up to more than zero.")
    return {ticker: weight / total for ticker, weight in cleaned.items()}


def _equity_share(classes: Mapping[str, float]) -> float:
    """Share of the invested weight that sits in equity ETFs, US or international."""
    invested = sum(classes.values())
    equity = sum(classes.get(c, 0.0) for c in etfs.EQUITY_CLASSES + etfs.INTERNATIONAL_CLASSES)
    return equity / invested if invested > 0 else 0.0


def _region_for(classes: Mapping[str, float]) -> str:
    """Factor region matching the clone's equity: US, Developed or Developed ex US.

    A clone with little equity, such as that of a bond fund, gets the US factors: the split
    of a few basis points of equity between regions is noise.
    """
    invested = sum(classes.values())
    equity = sum(classes.get(c, 0.0) for c in etfs.EQUITY_CLASSES + etfs.INTERNATIONAL_CLASSES)
    if invested <= 0 or equity < MIN_EQUITY_FOR_REGION * invested:
        return "US"
    share = sum(classes.get(c, 0.0) for c in etfs.INTERNATIONAL_CLASSES) / equity
    if share > 0.8:
        return "Developed ex US"
    return "Developed" if share > 0.35 else "US"


def _replicate(
    fund_prices: pd.Series,
    on_fund_days: pd.DataFrame,
    universe: list[str],
    config: ReplicationConfig,
    factor_loader: Callable[..., pd.DataFrame],
    notes: list[str],
) -> tuple[ReplicationResult, pd.DataFrame, str]:
    if not universe:
        raise ValueError("No price data for any of the ETFs the clone may use.")
    rf_daily = factor_loader("US", "daily")["RF"]
    fund = daily_returns(fund_prices)
    etf_returns = daily_returns(on_fund_days[universe])
    rf = compounded_rate(rf_daily, fund_prices.index).reindex(fund.index)
    if (fund.index[-1] - rf_daily.index[-1]).days > STALE_RATE_DAYS:
        notes.append(
            f"The daily T-bill rate in the French data ends {rf_daily.index[-1]:%Y-%m-%d} "
            "and is carried forward after that."
        )

    result = walk_forward(fund, etf_returns, rf, config, make_estimator(config))
    weeks = len(weekly_returns(result.returns))
    if weeks < 2:
        raise ValueError(
            f"Only {_count(weeks, 'week')} of out-of-sample returns so far; choose an earlier "
            "start date or a later end date."
        )
    dates = result.returns.index
    candidates = etf_returns.reindex(dates).dropna(axis=1)
    # chosen on weekly returns, like every tracking figure reported for it
    weekly = weekly_returns(candidates.assign(__fund__=fund.reindex(dates)))
    spread = weekly[candidates.columns].sub(weekly["__fund__"], axis=0).std().dropna()
    closest = str(spread.idxmin())
    returns = pd.DataFrame(
        {
            "fund": fund.reindex(dates),
            "clone": result.returns,
            "closest": candidates[closest],
            "rf": rf.reindex(dates),
        }
    )
    return result, returns, closest


def _attribute(
    fund_prices: pd.Series,
    prices: pd.DataFrame,
    on_fund_days: pd.DataFrame,
    region: str,
    frequency: str,
    use_bond_factors: bool,
    rolling_window: int,
    factor_loader: Callable[..., pd.DataFrame],
    notes: list[str],
) -> tuple[AttributionResult | None, pd.DataFrame, bool]:
    """The factor regression, rolling loadings and whether bond factors were used. The
    regression is None, with a note, when the history is too short for it."""
    factors = factor_loader(region, frequency)
    if frequency == "monthly":
        fund = monthly_returns(fund_prices)
    else:
        fund = daily_returns(fund_prices)
    excess = (fund - factors["RF"]).dropna()

    model = factors[FF6]
    if use_bond_factors:
        missing = [t for t in BOND_FACTOR_TICKERS if t not in prices]
        if missing:
            notes.append(
                f"No price data for {', '.join(missing)}, so the factor model has no term and "
                "credit factors."
            )
            use_bond_factors = False
        else:
            if frequency == "monthly":
                bonds = monthly_returns(prices[list(BOND_FACTOR_TICKERS)].dropna())
            else:
                bonds = daily_returns(on_fund_days[list(BOND_FACTOR_TICKERS)])
            bond = bond_factors(bonds["IEF"], bonds["LQD"], factors["RF"])
            model = model.join(bond, how="inner")

    if factors.index[-1] < fund.index[-1]:
        notes.append(
            f"The French factor data ends {factors.index[-1]:%Y-%m-%d}; "
            "later returns are left out of the factor attribution."
        )
    window = rolling_window if frequency == "monthly" else rolling_window * TRADING_DAYS_PER_MONTH
    try:
        attribution = factor_regression(excess, model, PERIODS_PER_YEAR[frequency])
    except ValueError:
        unit = "months" if frequency == "monthly" else "trading days"
        notes.append(
            f"The factor view is left out: it needs at least {model.shape[1] + 12} {unit} of "
            "returns that the factor data covers, and this history is shorter."
        )
        return None, pd.DataFrame(columns=model.columns, dtype=float), use_bond_factors
    return attribution, rolling_betas(excess, model, window), use_bond_factors
