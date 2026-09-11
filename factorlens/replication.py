"""Out-of-sample replication of a fund with a constrained portfolio of ETFs."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from numbers import Integral
from typing import NamedTuple

import numpy as np
import pandas as pd
from scipy.optimize import minimize

from factorlens.data import weekly_returns
from factorlens.metrics import TRADING_DAYS


@dataclass(frozen=True)
class ReplicationConfig:
    """Settings for the walk-forward replication.

    window: trailing trading days used to estimate the weights.
    rebalance: "M" for month-end or "Q" for quarter-end signals.
    frequency: returns the weights are fitted to, "daily" or "weekly" (weeks ending
        on Friday). Weekly returns absorb the timing mismatch between markets that
        close at different hours. "auto" is resolved by run_analysis (weekly when the
        fund or a holding of the portfolio is priced outside US trading hours) and
        means daily here.
    execution_lag: trading days between signal and trade. With the default of one,
        weights estimated from data through the close of day t are traded at the
        close of day t+1 and first earn returns on day t+2.
    long_only: forbid short positions.
    max_gross: cap on the sum of absolute ETF weights; 1 means no leverage.
    financing_spread: annual spread over the T-bill rate paid on borrowed cash and,
        as a borrow fee, on short positions.
    cost_bps: trading cost in basis points of traded value.
    max_etfs: cap on the number of ETFs in the clone (None: no cap).
    min_weight: positions below this weight are dropped and the rest refitted.
    overlap: fit daily data on overlapping sums of this many days (1: plain daily
        returns). Multi-day returns absorb prices set at different times of day.

    max_etfs, min_weight and overlap apply to long-only, unlevered clones, which use the
    estimators in factorlens.estimators; long/short or levered clones use plain least
    squares.
    """

    window: int = 378
    rebalance: str = "M"
    frequency: str = "auto"
    execution_lag: int = 1
    long_only: bool = True
    max_gross: float = 1.0
    financing_spread: float = 0.005
    cost_bps: float = 5.0
    max_etfs: int | None = None
    min_weight: float = 0.02
    overlap: int = 1

    def __post_init__(self) -> None:
        counts = (self.window, self.execution_lag, self.overlap)
        cap = self.max_etfs
        checks = {
            "window, execution_lag and overlap must be whole numbers": all(
                isinstance(value, Integral) for value in counts
            ),
            "max_etfs must be a whole number": cap is None or isinstance(cap, Integral),
            "max_etfs needs a long-only, unlevered clone": cap is None
            or (self.long_only and self.max_gross == 1.0),
            "financing_spread cannot be negative": self.financing_spread >= 0,
            "the window needs at least 20 trading days": self.window >= 20,
            'rebalance must be "M" or "Q"': self.rebalance in ("M", "Q"),
            'frequency must be "auto", "daily" or "weekly"': self.frequency
            in ("auto", "daily", "weekly"),
            "execution_lag cannot be negative": self.execution_lag >= 0,
            "max_gross must be positive": self.max_gross > 0,
            "cost_bps cannot be negative": self.cost_bps >= 0,
            "max_etfs must be at least 1": self.max_etfs is None or self.max_etfs >= 1,
            "min_weight must lie between 0 and 1": 0 <= self.min_weight < 1,
            "overlap must be at least 1": self.overlap >= 1,
        }
        failed = [message for message, ok in checks.items() if not ok]
        if failed:
            raise ValueError(f"Invalid replication settings: {'; '.join(failed)}.")


@dataclass
class ReplicationResult:
    weights: pd.DataFrame  # ETF weights set at the close of each trade date; cash is 1 - row sum
    returns: pd.Series  # daily clone returns after the first trade date
    turnover: pd.Series  # traded value / NAV on each trade date, starting from all cash
    config: ReplicationConfig

    @property
    def cash(self) -> pd.Series:
        return 1.0 - self.weights.sum(axis=1)

    @property
    def gross_exposure(self) -> pd.Series:
        return self.weights.abs().sum(axis=1)

    @property
    def annual_turnover(self) -> float:
        """Traded value per calendar year as a multiple of NAV, excluding the initial purchase."""
        days = (self.returns.index[-1] - self.weights.index[0]).days
        return float(self.turnover.iloc[1:].sum() / (max(days, 1) / 365.25))


class Simulation(NamedTuple):
    returns: pd.Series
    turnover: pd.Series


# An estimator maps the trailing excess returns of the fund (y, length T) and of the ETFs
# that have data over the whole window (X, T x N) to weights for those ETFs. `previous`
# holds the weights set at the last rebalance for the same ETFs, zero for ETFs that were
# not available then.
Estimator = Callable[[np.ndarray, np.ndarray, np.ndarray, ReplicationConfig], np.ndarray]


def estimate_weights(
    y: np.ndarray, X: np.ndarray, long_only: bool = True, max_gross: float = 1.0
) -> np.ndarray:
    """Weights w minimising the squared tracking error ||y - X w||^2.

    y and X hold excess returns over the risk-free rate, so the unallocated remainder
    1 - sum(w) is a cash position. Subject to sum(|w|) <= max_gross and, if long_only,
    w >= 0. Short positions are handled by splitting w = u - v with u, v >= 0, which
    keeps the problem a smooth quadratic program.
    """
    y = np.asarray(y, dtype=float)
    X = np.asarray(X, dtype=float)
    n = X.shape[1]
    split = np.eye(n) if long_only else np.hstack([np.eye(n), -np.eye(n)])
    scale = float(np.mean(y**2)) or 1.0  # keeps the objective O(1) for the solver's tolerances
    Q = split.T @ (X.T @ X) @ split / (len(y) * scale)
    c = split.T @ (X.T @ y) / (len(y) * scale)
    m = split.shape[1]
    result = minimize(
        lambda z: z @ Q @ z - 2 * c @ z,
        x0=np.zeros(m),
        jac=lambda z: 2 * (Q @ z - c),
        bounds=[(0.0, None)] * m,
        constraints=[
            {"type": "ineq", "fun": lambda z: max_gross - z.sum(), "jac": lambda z: -np.ones(m)}
        ],
        method="SLSQP",
        options={"ftol": 1e-12, "maxiter": 1000},
    )
    z = np.clip(result.x, 0.0, None)
    if z.sum() > max_gross:
        z *= max_gross / z.sum()
    return split @ z


def constrained_least_squares(
    y: np.ndarray, X: np.ndarray, previous: np.ndarray, config: ReplicationConfig
) -> np.ndarray:
    """Plain least squares under the config's long-only and exposure limits.

    The benchmark's baseline, and the estimator for long/short or levered clones. Long-only,
    unlevered clones use estimators.stable_least_squares by default.
    """
    return estimate_weights(y, X, config.long_only, config.max_gross)


def rebalance_dates(index: pd.DatetimeIndex, frequency: str, window: int) -> pd.DatetimeIndex:
    """Last trading day of each month ("M") or quarter ("Q") once `window` observations exist.

    The final date of the index is excluded because no returns follow it.
    """
    period_ends = index.to_series().groupby(index.to_period(frequency)).max()
    ends = pd.DatetimeIndex(period_ends.to_numpy())
    return ends[(ends >= index[window - 1]) & (ends < index[-1])]


def simulate_clone(
    target_weights: pd.DataFrame,
    asset_returns: pd.DataFrame,
    rf: pd.Series,
    financing_spread: float = 0.0,
    cost_bps: float = 0.0,
) -> Simulation:
    """Daily returns of a portfolio traded to `target_weights` at the close of each of its dates.

    Positions drift with prices between trades. Cash (1 - sum of weights) earns the
    T-bill rate `rf`; when negative it costs rf plus `financing_spread`, and short
    positions pay the spread as a borrow fee. Each trade costs `cost_bps` of the traded
    value. The first return is for the day after the first trade and includes the cost
    of building the initial portfolio. Missing asset returns (before an ETF started
    trading, when its weight is zero) count as zero.
    """
    assets = list(target_weights.columns)
    returns = asset_returns[assets].fillna(0.0)
    rf = rf.reindex(returns.index)
    daily_spread = financing_spread / TRADING_DAYS
    cost = cost_bps / 1e4
    targets = {date: row.to_numpy(dtype=float) for date, row in target_weights.iterrows()}
    start = target_weights.index[0]

    holdings = np.zeros(len(assets))
    cash = nav = 1.0
    dates, daily, turnover = [], [], {}
    for date, r, f in zip(returns.index, returns.to_numpy(), rf.to_numpy(), strict=True):
        if date < start:
            continue
        if date > start:
            holdings = holdings * (1 + r)
            short = -holdings[holdings < 0].sum()
            cash = cash * (1 + f + (daily_spread if cash < 0 else 0.0)) - daily_spread * short
        value = holdings.sum() + cash
        if date in targets:
            target = targets[date] * value
            traded = np.abs(target - holdings).sum()
            cash = value - target.sum() - cost * traded
            holdings = target
            turnover[date] = traded / value
            value = holdings.sum() + cash
        if date > start:
            dates.append(date)
            daily.append(value / nav - 1)
            nav = value
    return Simulation(
        pd.Series(daily, index=pd.DatetimeIndex(dates), name="clone"),
        pd.Series(turnover, name="turnover"),
    )


def walk_forward(
    fund_returns: pd.Series,
    asset_returns: pd.DataFrame,
    rf: pd.Series,
    config: ReplicationConfig | None = None,
    estimator: Estimator | None = None,
) -> ReplicationResult:
    """Estimate weights at each signal date from trailing data and simulate the clone.

    Inputs are daily simple returns. ETFs may start trading later than the fund (NaN
    before that); at each signal date only ETFs with data over the whole estimation
    window are passed to the estimator, the others get zero weight. Weights estimated
    at a signal date use only data up to and including that date, and only returns
    after the first trade are reported, so every clone return is out of sample. With
    weekly frequency the weights are fitted to the weeks that lie inside the window;
    the simulation itself is always daily. Without an `estimator`, the one the app uses
    for this config is taken (estimators.make_estimator).
    """
    config = config or ReplicationConfig()
    if estimator is None:
        from factorlens.estimators import make_estimator  # estimators imports this module

        estimator = make_estimator(config)
    assets = list(asset_returns.columns)
    data = pd.concat([fund_returns.rename("__fund__"), asset_returns, rf.rename("__rf__")], axis=1)
    data = data[data["__fund__"].notna() & data["__rf__"].notna()]
    needed = config.window + config.execution_lag + 2
    if len(data) < needed:
        raise ValueError(
            f"Only {len(data)} trading days of fund data; a clone with a {config.window}-day "
            f"estimation window needs at least {needed}, and more for a useful out-of-sample "
            "record. Choose an earlier start date."
        )

    weekly = config.frequency == "weekly"
    sample = weekly_returns(data) if weekly else data
    sample = sample[sample["__fund__"].notna() & sample["__rf__"].notna()]
    fund_excess = (sample["__fund__"] - sample["__rf__"]).to_numpy()
    asset_excess = sample[assets].sub(sample["__rf__"], axis=0).to_numpy()
    # A week is labelled with its Friday; it counts if its Monday lies inside the window.
    week_start = pd.Timedelta(days=4 if weekly else 0)

    weights = {}
    previous = np.zeros(len(assets))
    for signal in rebalance_dates(data.index, config.rebalance, config.window):
        pos = data.index.get_loc(signal)
        if pos + config.execution_lag >= len(data) - 1:
            break
        first = data.index[pos - config.window + 1]
        rows = (sample.index - week_start >= first) & (sample.index <= signal)
        if rows.sum() < 2:
            continue
        X = asset_excess[rows]
        eligible = np.isfinite(X).all(axis=0)
        if not eligible.any():
            continue
        w = np.zeros(len(assets))
        w[eligible] = estimator(fund_excess[rows], X[:, eligible], previous[eligible], config)
        weights[data.index[pos + config.execution_lag]] = w
        previous = w
    if not weights:
        raise ValueError("No rebalance date has a full estimation window; extend the date range.")

    target_weights = pd.DataFrame.from_dict(weights, orient="index", columns=assets)
    simulation = simulate_clone(
        target_weights, data[assets], data["__rf__"], config.financing_spread, config.cost_bps
    )
    return ReplicationResult(target_weights, simulation.returns, simulation.turnover, config)
