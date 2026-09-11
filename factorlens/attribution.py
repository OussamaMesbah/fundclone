"""Factor attribution: regress fund excess returns on long/short factor returns."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd
import statsmodels.api as sm
from statsmodels.regression.rolling import RollingOLS

FACTOR_NAMES = {
    "Mkt-RF": "Market",
    "SMB": "Size",
    "HML": "Value",
    "RMW": "Profitability",
    "CMA": "Investment",
    "MOM": "Momentum",
    "TERM": "Term",
    "DEF": "Credit",
}

FACTOR_DESCRIPTIONS = {
    "Mkt-RF": "Market portfolio minus the one-month T-bill",
    "SMB": "Small minus big stocks by market capitalisation",
    "HML": "High minus low book-to-market",
    "RMW": "Robust minus weak operating profitability",
    "CMA": "Conservative minus aggressive asset growth",
    "MOM": "Winners minus losers over the past 12 months, skipping the last",
    "TERM": "7-10y Treasuries (IEF) minus the one-month T-bill",
    "DEF": "Investment-grade corporates (LQD) minus 7-10y Treasuries (IEF)",
}

BOND_FACTOR_TICKERS = ("IEF", "LQD")


def bond_factors(ief: pd.Series, lqd: pd.Series, rf: pd.Series) -> pd.DataFrame:
    """Term and credit spreads built from ETFs, after Fama & French (1993).

    TERM is the 7-10 year Treasury ETF over the T-bill rate, DEF the investment-grade
    corporate ETF over the Treasury ETF. Inputs are simple returns at one frequency.
    """
    data = pd.concat({"IEF": ief, "LQD": lqd, "RF": rf}, axis=1, join="inner").dropna()
    return pd.DataFrame({"TERM": data["IEF"] - data["RF"], "DEF": data["LQD"] - data["IEF"]})


def newey_west_lags(n_obs: int) -> int:
    """Lag length floor(4 * (T / 100) ** (2 / 9)), the Newey-West (1994) rule of thumb."""
    return int(4 * (n_obs / 100) ** (2 / 9))


@dataclass
class AttributionResult:
    """Full-sample factor regression with Newey-West (HAC) standard errors."""

    alpha: float  # annualised intercept
    alpha_tstat: float
    alpha_pvalue: float
    betas: pd.Series
    std_errors: pd.Series
    t_stats: pd.Series
    p_values: pd.Series
    r_squared: float
    adj_r_squared: float
    residual_vol: float  # annualised
    contributions: pd.Series  # annualised; the factors plus "Alpha", summing to mean_excess_return
    mean_excess_return: float  # annualised arithmetic mean
    n_obs: int
    periods_per_year: int
    hac_lags: int
    start: pd.Timestamp
    end: pd.Timestamp

    def table(self) -> pd.DataFrame:
        """One row per factor and one for alpha: loading, t-stat, p-value, contribution p.a."""
        factors = pd.DataFrame(
            {
                "Factor": [FACTOR_NAMES.get(f, f) for f in self.betas.index],
                "Loading": self.betas,
                "t-stat": self.t_stats,
                "p-value": self.p_values,
                "Contribution p.a.": self.contributions[self.betas.index],
            }
        )
        alpha = pd.DataFrame(
            {
                "Factor": ["Alpha"],
                "Loading": [np.nan],
                "t-stat": [self.alpha_tstat],
                "p-value": [self.alpha_pvalue],
                "Contribution p.a.": [self.alpha],
            },
            index=["Alpha"],
        )
        return pd.concat([factors, alpha])


def factor_regression(
    excess_returns: pd.Series,
    factors: pd.DataFrame,
    periods_per_year: int = 12,
    hac_lags: int | None = None,
) -> AttributionResult:
    """OLS of fund excess returns on factor returns with Newey-West standard errors.

    With an intercept in the model, the mean excess return splits exactly into
    loading times mean factor return for each factor plus alpha; `contributions`
    reports that split, annualised.
    """
    data = pd.concat([excess_returns.rename("__y__"), factors], axis=1, join="inner").dropna()
    n_factors = factors.shape[1]
    if len(data) < n_factors + 12:
        raise ValueError(
            f"Only {len(data)} overlapping observations for {n_factors} factors; "
            "extend the date range."
        )
    y = data["__y__"]
    X = sm.add_constant(data[factors.columns], has_constant="add")
    lags = newey_west_lags(len(data)) if hac_lags is None else hac_lags
    fit = sm.OLS(y, X).fit(cov_type="HAC", cov_kwds={"maxlags": lags})

    betas = fit.params.drop("const")
    alpha = float(fit.params["const"])
    contributions = (
        pd.concat([betas * data[factors.columns].mean(), pd.Series({"Alpha": alpha})])
        * periods_per_year
    )
    return AttributionResult(
        alpha=alpha * periods_per_year,
        alpha_tstat=float(fit.tvalues["const"]),
        alpha_pvalue=float(fit.pvalues["const"]),
        betas=betas,
        std_errors=fit.bse.drop("const"),
        t_stats=fit.tvalues.drop("const"),
        p_values=fit.pvalues.drop("const"),
        r_squared=float(fit.rsquared),
        adj_r_squared=float(fit.rsquared_adj),
        residual_vol=float(np.sqrt(fit.mse_resid * periods_per_year)),
        contributions=contributions,
        mean_excess_return=float(y.mean() * periods_per_year),
        n_obs=int(fit.nobs),
        periods_per_year=periods_per_year,
        hac_lags=lags,
        start=data.index[0],
        end=data.index[-1],
    )


def rolling_betas(excess_returns: pd.Series, factors: pd.DataFrame, window: int) -> pd.DataFrame:
    """Factor loadings re-estimated on each trailing window of `window` observations."""
    data = pd.concat([excess_returns.rename("__y__"), factors], axis=1, join="inner").dropna()
    if len(data) < window:
        return pd.DataFrame(columns=factors.columns, dtype=float)
    X = sm.add_constant(data[factors.columns], has_constant="add")
    params = RollingOLS(data["__y__"], X, window=window).fit(params_only=True).params
    return params.drop(columns="const").dropna(how="all")
