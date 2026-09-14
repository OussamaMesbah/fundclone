"""Performance and tracking statistics for daily return series."""

from __future__ import annotations

import numpy as np
import pandas as pd

TRADING_DAYS = 252
WEEKS_PER_YEAR = 52
_FLAT = 1e-12  # variance below which a series counts as not moving at all


def drawdown(returns: pd.Series) -> pd.Series:
    """Decline of the growth path from its running peak, starting from a peak of 1."""
    wealth = (1 + returns).cumprod()
    return wealth / wealth.cummax().clip(lower=1.0) - 1


def years_spanned(index: pd.Index, periods_per_year: int = TRADING_DAYS) -> float:
    """Years covered by returns with this index.

    For dates, calendar time: the span from first to last date, stretched by one average
    period for the first return. Days that are missing or merged into the next therefore do
    not shorten it. Without dates, `periods_per_year` observations make a year.
    """
    n = len(index)
    if isinstance(index, pd.DatetimeIndex) and n > 1:
        days = (index[-1] - index[0]).days
        if days > 0:
            return days / 365.25 * n / (n - 1)
    return n / periods_per_year


def newey_west_variance(values: np.ndarray, lags: int | None = None) -> float:
    """Long-run variance of a series: its variance plus the autocovariances up to `lags`,
    with Bartlett weights (Newey and West, 1987). The default number of lags,
    floor(4 (n / 100)^(2/9)), follows Newey and West (1994): 6 for 16 years of weeks.

    For independent observations it is close to the plain variance; when a gap in one week
    tends to carry over into the next, it is larger, and so is the uncertainty of the mean.
    """
    x = np.asarray(values, dtype=float)
    x = x - x.mean()
    n = len(x)
    if lags is None:
        lags = int(4 * (n / 100) ** (2 / 9))
    variance = float(x @ x) / n
    for k in range(1, min(lags, n - 1) + 1):
        variance += 2 * (1 - k / (lags + 1)) * float(x[k:] @ x[:-k]) / n
    return max(variance, 0.0)


def performance(
    returns: pd.Series, rf: pd.Series, periods_per_year: int = TRADING_DAYS
) -> dict[str, float]:
    """Annualised return (geometric), volatility, Sharpe ratio, max drawdown, total return.

    With a date index, years are calendar years (see years_spanned) and volatility is
    annualised with the observed number of returns per year. Less than a year of returns
    is not compounded into an annual return, which is then NaN.
    """
    data = pd.concat([returns.rename("r"), rf.rename("rf")], axis=1, join="inner").dropna()
    r, excess = data["r"], data["r"] - data["rf"]
    total = float((1 + r).prod() - 1)
    years = years_spanned(r.index, periods_per_year)
    per_year = len(r) / years
    excess_vol = excess.std()
    return {
        "annual_return": (1 + total) ** (1 / years) - 1 if years >= 1 else float("nan"),
        "volatility": float(r.std() * np.sqrt(per_year)),
        "sharpe": float(excess.mean() / excess_vol * np.sqrt(per_year))
        if excess_vol > 1e-12  # rounding leaves a tiny positive std for constant returns
        else float("nan"),
        "max_drawdown": float(drawdown(r).min()),
        "total_return": total,
    }


def tracking(
    fund: pd.Series, clone: pd.Series, periods_per_year: int = TRADING_DAYS
) -> dict[str, float]:
    """How closely `clone` follows `fund`.

    tracking_error is the annualised standard deviation of fund minus clone, and r_squared
    1 - var(fund - clone) / var(fund); out of sample it can be negative, and it is NaN for
    a fund that does not move. fund_return and clone_return are compound annual growth
    rates, and active_return is their difference: unlike the mean of fund minus clone it
    does not favour the more volatile of the two. log_gap is the annualised mean difference
    of log returns and active_risk its annualised standard deviation. log_gap_se is the
    standard error of log_gap from the Newey-West long-run variance, which allows for gaps
    that carry over from one period to the next; the t-statistic and report.interval use it.
    """
    data = pd.concat([fund.rename("fund"), clone.rename("clone")], axis=1, join="inner").dropna()
    active = data["fund"] - data["clone"]
    log_fund, log_clone = np.log1p(data["fund"]), np.log1p(data["clone"])
    gap = log_fund - log_clone
    fund_return = float(np.expm1(log_fund.mean() * periods_per_year))
    clone_return = float(np.expm1(log_clone.mean() * periods_per_year))
    tracking_error = float(active.std() * np.sqrt(periods_per_year))
    log_gap = float(gap.mean() * periods_per_year)
    spread = gap.std()
    active_risk = float(spread * np.sqrt(periods_per_year))
    log_gap_se = float(np.sqrt(newey_west_variance(gap.to_numpy()) / len(gap)) * periods_per_year)
    flat = not data["fund"].var() > _FLAT
    return {
        "tracking_error": tracking_error,
        "correlation": float("nan") if flat else float(data["fund"].corr(data["clone"])),
        "r_squared": float("nan") if flat else float(1 - active.var() / data["fund"].var()),
        "fund_return": fund_return,
        "clone_return": clone_return,
        "active_return": fund_return - clone_return,
        "log_gap": log_gap,
        "active_risk": active_risk,
        "log_gap_se": log_gap_se,
        "information_ratio": log_gap / active_risk if active_risk > 0 else float("nan"),
        # t-statistic of the mean return difference: is the gap more than noise?
        "active_tstat": log_gap / log_gap_se if log_gap_se > _FLAT else float("nan"),
        "observations": len(active),
        "periods_per_year": periods_per_year,
    }


def benchmark_fit(
    fund: pd.Series, benchmark: pd.Series, periods_per_year: int = TRADING_DAYS
) -> dict[str, float]:
    """Regression of fund on benchmark returns: beta, R² (squared correlation) and tracking
    error, the three statistics of ESMA's screen for potential closet index funds."""
    data = pd.concat([fund.rename("f"), benchmark.rename("b")], axis=1, join="inner").dropna()
    flat = not data["f"].var() > _FLAT
    return {
        "beta": float(data["f"].cov(data["b"]) / data["b"].var()),
        "r_squared": float("nan") if flat else float(data["f"].corr(data["b"]) ** 2),
        "tracking_error": float((data["f"] - data["b"]).std() * np.sqrt(periods_per_year)),
    }
