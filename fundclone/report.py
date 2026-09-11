"""Plain-language verdict on an analysis, shared by the app and the command line."""

from __future__ import annotations

import math

from scipy import stats

from fundclone.analysis import Analysis
from fundclone.metrics import years_spanned

# ESMA's returns-based screen for potential closet index funds (TRV No. 2, 2020): against
# the benchmark, tracking error below 3%, R² above 95% and beta between 0.95 and 1.05.
ESMA_TRACKING_ERROR = 0.03
ESMA_R_SQUARED = 0.95
ESMA_BETA = (0.95, 1.05)
EQUITY_SHARE_FOR_SCREEN = 0.7  # the screen was designed for equity funds
PASSIVE_FEE = 0.002  # funds that charge at most 0.20% a year are mostly index funds
SHORT_SAMPLE_WEEKS = 52  # fewer out-of-sample weeks are too few to judge a fund by


def interval(tracking: dict[str, float]) -> tuple[float, float]:
    """95% confidence range of the fund-minus-clone difference in compound annual return.

    The range is a Student's t interval for the mean log return gap, turned into a
    difference of annual returns at the clone's growth rate.
    """
    n = tracking["observations"]
    years = n / tracking["periods_per_year"]
    half = stats.t.ppf(0.975, max(n - 1, 1)) * tracking["active_risk"] / math.sqrt(years)
    base = 1 + tracking["clone_return"]
    return (
        base * math.expm1(tracking["log_gap"] - half),
        base * math.expm1(tracking["log_gap"] + half),
    )


def too_short(a: Analysis) -> bool:
    """Less than a year of out-of-sample returns, counted in weeks or in calendar time."""
    return a.tracking["observations"] < SHORT_SAMPLE_WEEKS or years_spanned(a.returns.index) < 1


def _signed(value: float) -> str:
    """A percentage with its sign, without a "-0.0%" for tiny losses."""
    return f"{round(value, 3) + 0.0:+.1%}"


def looks_passive(a: Analysis) -> bool:
    """An index fund or index ETF, judged by its name or its fee."""
    name = (a.name or "").lower()
    return "index" in name or (a.expense_ratio is not None and a.expense_ratio <= PASSIVE_FEE)


def closet_index_check(a: Analysis) -> dict | None:
    """ESMA's three screens against the closest single ETF, or None for portfolios, for
    funds whose clone is mostly not equity, and for less than a year of out-of-sample
    returns. "passive" marks funds that look like index funds, for which meeting the
    screen is expected."""
    if a.holdings or a.equity_share < EQUITY_SHARE_FOR_SCREEN or too_short(a):
        return None
    fit = a.benchmark_fit
    checks = {
        "tracking error below 3%": fit["tracking_error"] < ESMA_TRACKING_ERROR,
        "R² above 95%": fit["r_squared"] > ESMA_R_SQUARED,
        "beta between 0.95 and 1.05": ESMA_BETA[0] <= fit["beta"] <= ESMA_BETA[1],
    }
    return {**fit, "checks": checks, "flagged": all(checks.values()), "passive": looks_passive(a)}


def headline(a: Analysis) -> list[str]:
    """Sentences that answer: how close is the clone, what does it cost, and does the fund
    beat it after fees."""
    t, closest = a.tracking, a.closest_tracking
    count = len(a.current_weights)
    subject = "The portfolio" if a.holdings else a.label
    inner = "the portfolio" if a.holdings else a.label  # the subject in mid-sentence
    possessive = "the portfolio's" if a.holdings else f"{a.label}'s"
    if count:
        clone = f"A clone of {count} ETF{'' if count == 1 else 's'}"
    elif (a.replication.weights.abs().sum(axis=1) > 1e-4).any():
        clone = "The clone, in T-bills since its latest rebalance,"
    else:
        clone = "A clone in T-bills"
    if a.expense_ratio is not None:
        fees = (
            f"The clone costs {a.clone_expense_ratio:.2%} a year in ETF fees; "
            f"the fund charges {a.expense_ratio:.2%}."
        )
    else:
        fees = f"The clone costs {a.clone_expense_ratio:.2%} a year in ETF fees."

    if too_short(a):
        weeks = t["observations"]
        years = weeks / t["periods_per_year"]
        fund, clone_growth = ((1 + t[key]) ** years - 1 for key in ("fund_return", "clone_return"))
        return [
            f"There are only {weeks} weeks of out-of-sample returns so far, too few to rely on.",
            f"{clone} has tracked {possessive} weekly returns with a tracking error of "
            f"{t['tracking_error']:.1%} a year.",
            fees,
            f"Over these weeks {inner} returned {_signed(fund)} and its clone "
            f"{_signed(clone_growth)} after all fees.",
        ]

    if math.isfinite(t["r_squared"]):
        fit = f"explains {t['r_squared']:.0%} of the variation in {possessive} weekly returns"
    else:
        fit = f"follows {possessive} weekly returns"
    lines = [
        f"{clone} {fit} out of sample, with a tracking error of {t['tracking_error']:.1%} a year.",
        fees,
    ]
    gap = t["active_return"]
    low, high = interval(t)
    evidence = "more than noise" if low > 0 or high < 0 else "within the noise"
    lines.append(
        f"{subject} returned {abs(gap):.1%} a year {'more' if gap >= 0 else 'less'} than its "
        f"clone after all fees; the 95% range is {_signed(low)} to {_signed(high)}, so the gap "
        f"is {evidence}."
    )
    lines.append(
        f"The closest single ETF, {a.closest_etf}, tracks with "
        f"{closest['tracking_error']:.1%} tracking error."
    )
    return lines
