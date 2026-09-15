"""Out-of-sample replication benchmark on a fixed set of US mutual funds.

For every fund in funds.csv the walk-forward clone is run with one estimator and one
ETF set, and tracking statistics are computed over a common evaluation period: from
January 2010, or three years after a younger fund's first price. Every estimator whose
window fits into those three years is therefore compared on the same days. Tracking
error is reported on daily, weekly and monthly returns; weekly is the headline figure,
because daily closing prices carry timing noise that is not tracking error.

    python -m benchmarks.run --split dev
    python -m benchmarks.run --split dev --estimator my_estimator.py:estimate --out mine.csv

The price snapshot is read from benchmarks/data (see benchmarks.download) unless --prices
and --rf point elsewhere.
"""

from __future__ import annotations

import argparse
import importlib.util
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import numpy as np
import pandas as pd

from fundclone import etfs
from fundclone.data import (
    adjust_splits,
    compounded_rate,
    daily_returns,
    drop_price_errors,
    drop_reversed_moves,
    drop_stale_prices,
    fx_ticker,
    to_usd,
    unadjusted_distribution,
    weekly_returns,
)
from fundclone.estimators import make_estimator
from fundclone.metrics import WEEKS_PER_YEAR, tracking, years_spanned
from fundclone.replication import ReplicationConfig, constrained_least_squares, walk_forward
from fundclone.report import interval

FUNDS_FILE = Path(__file__).with_name("funds.csv")
DATA_DIR = Path(__file__).with_name("data")  # where benchmarks.download puts the snapshot
SPLITS = ("dev", "holdout", "fresh")
DATA_START = pd.Timestamp("2006-01-01")
EVAL_START = pd.Timestamp("2010-01-04")
WARMUP = pd.Timedelta(days=1100)  # about three years of data before a young fund is scored

# The baseline: four to seven hand-picked ETFs per type of fund, fitted by plain least
# squares, the way the project (then FactorLens) worked before 0.3; 0.1.0's sets differed.
LEGACY = {
    "US equity: style ETFs": ["SPY", "IWM", "IWD", "IWF"],
    "Global equity": ["SPY", "IWM", "EFA", "EEM"],
    "Fixed income": ["SHY", "IEF", "TLT", "TIP", "LQD", "HYG"],
    "Multi-asset": ["SPY", "EFA", "EEM", "IEF", "TIP", "LQD", "HYG"],
}

_state: dict = {}


def load_estimator(spec: str | None):
    """The estimator the app uses for "product", a candidate for `path/to/file.py:function`,
    and plain constrained least squares (the baseline's estimator) for None."""
    if not spec:
        return constrained_least_squares
    if spec == "product":
        return lambda y, X, previous, config: make_estimator(config)(y, X, previous, config)
    path, _, name = spec.partition(":")
    module_spec = importlib.util.spec_from_file_location(Path(path).stem, path)
    module = importlib.util.module_from_spec(module_spec)
    module_spec.loader.exec_module(module)
    return getattr(module, name or "estimate")


def checked(estimator):
    """Wrap an estimator so that every weight vector must be long-only and unlevered."""

    def estimate(y, X, previous, config):
        w = np.asarray(estimator(y, X, previous, config), dtype=float)
        if w.shape != (X.shape[1],) or not np.isfinite(w).all():
            raise ValueError(f"estimator returned shape {w.shape} or non-finite weights")
        if w.min() < -1e-6 or w.sum() > 1 + 1e-6:
            raise ValueError(f"weights violate w >= 0, sum <= 1 (min {w.min()}, sum {w.sum()})")
        return np.clip(w, 0.0, None)

    return estimate


def universe_for(
    name: str,
    legacy: str,
    prices: pd.DataFrame | None = None,
    etf_set: str = etfs.DEFAULT_SET,
) -> list[str]:
    """ "legacy" (the fund's old hand-picked set), "all" (every ETF of `etf_set`),
    "traded-by:DATE" (every ETF of the set with a price on or before DATE, the list an
    investor could have known then) or a comma list."""
    if name == "legacy":
        return LEGACY[legacy]
    if name == "all":
        return etfs.tickers(etf_set=etf_set)
    if name.startswith("traded-by:"):
        date = pd.Timestamp(name.partition(":")[2])
        return [
            ticker
            for ticker in etfs.tickers(etf_set=etf_set)
            if prices is not None
            and ticker in prices
            and prices[ticker].first_valid_index() <= date
        ]
    return [ticker.strip() for ticker in name.split(",")]


def _init(
    prices_path: str,
    rf_path: str,
    estimator: str | None,
    config: ReplicationConfig,
    clean: bool,
    etf_set: str = etfs.DEFAULT_SET,
    eval_start: pd.Timestamp = EVAL_START,
    eval_end: pd.Timestamp | None = None,
):
    prices = etfs.without_known_errors(pd.read_parquet(prices_path))
    for etf in etfs.ETFS:  # ETFs quoted in another currency, such as UCITS ETFs in EUR
        rate = fx_ticker(etf.currency)
        if rate and etf.ticker in prices and rate in prices:
            prices[etf.ticker] = to_usd(prices[etf.ticker].dropna(), prices[rate])
    _state["prices"] = prices[prices.index >= DATA_START]
    _state["etf_set"] = etf_set
    _state["eval_start"] = pd.Timestamp(eval_start)
    _state["eval_end"] = pd.Timestamp(eval_end) if eval_end else None
    _state["rf"] = pd.read_csv(rf_path, index_col=0, parse_dates=True).iloc[:, 0]
    _state["estimator"] = checked(load_estimator(estimator))
    _state["config"] = config
    _state["clean"] = clean


def evaluate(fund: dict, universe: str) -> dict:
    prices, rf = _state["prices"], _state["rf"]
    ticker = fund["ticker"]
    row = {key: fund[key] for key in ("ticker", "category", "split")}
    try:
        assets = [
            t
            for t in universe_for(universe, fund["legacy_universe"], prices, _state["etf_set"])
            if t in prices and t != ticker
        ]
        fund_prices = prices[ticker].dropna()
        if _state["clean"]:
            market = daily_returns(prices[assets].ffill().reindex(fund_prices.index))
            stock = fund["category"] == "Single stock"  # the app checks funds and ETFs only
            if not stock:
                checked = drop_price_errors(fund_prices, market)
                fund_prices = drop_reversed_moves(checked, prices[assets])
            fund_prices = drop_stale_prices(fund_prices, market)
            if not stock:
                fund_prices = adjust_splits(fund_prices, market)[0]
                if found := unadjusted_distribution(fund_prices, prices[assets]):
                    fund_prices = fund_prices[fund_prices.index < found[0]]
        fund_returns = daily_returns(fund_prices)
        etf_returns = daily_returns(prices[assets].ffill().reindex(fund_prices.index))
        rf_daily = compounded_rate(rf, fund_prices.index).reindex(fund_returns.index)
        start = max(_state["eval_start"], fund_prices.index[0] + WARMUP)
        result = walk_forward(
            fund_returns, etf_returns, rf_daily, _state["config"], _state["estimator"]
        )
        if result.returns.index[0] > start:
            raise ValueError(
                f"clone starts {result.returns.index[0]:%Y-%m-%d}, after {start:%Y-%m-%d}"
            )
        end = _state["eval_end"] or result.returns.index[-1]
        clone = result.returns[(result.returns.index >= start) & (result.returns.index <= end)]
        pair = pd.DataFrame({"fund": fund_returns.reindex(clone.index), "clone": clone})
        weekly = weekly_returns(pair)
        monthly = (1 + pair).resample("ME").prod() - 1
        weights = result.weights[(result.weights.index >= start) & (result.weights.index <= end)]
        years = years_spanned(clone.index)  # calendar years: merged stale days still count
        trades = (result.turnover.index >= start) & (result.turnover.index <= end)
        # The simplest alternative, as in the app's verdict: the single ETF that tracked the
        # fund best over the scored weeks, chosen with hindsight.
        singles = weekly_returns(etf_returns.reindex(clone.index).dropna(axis=1))
        closest = str(singles.sub(weekly["fund"], axis=0).std().idxmin())
        versus_clone = tracking(weekly["fund"], weekly["clone"], WEEKS_PER_YEAR)
        versus_closest = tracking(weekly["fund"], singles[closest], WEEKS_PER_YEAR)
        gap_low, gap_high = interval(versus_clone)
        closest_low, closest_high = interval(versus_closest)
        row.update(tracking(pair["fund"], pair["clone"]))
        row.update(
            te_weekly=versus_clone["tracking_error"],
            r2_weekly=versus_clone["r_squared"],
            te_monthly=float((monthly["fund"] - monthly["clone"]).std() * np.sqrt(12)),
            turnover=float(result.turnover[trades].sum() / years),
            realised=float(result.realised[trades].sum() / years),
            holdings=float((weights.abs() > 0.01).sum(axis=1).mean()),
            gap=versus_clone["active_return"],
            gap_low=gap_low,
            gap_high=gap_high,
            closest=closest,
            te_closest=versus_closest["tracking_error"],
            r2_closest=versus_closest["r_squared"],
            gap_closest=versus_closest["active_return"],
            gap_closest_low=closest_low,
            gap_closest_high=closest_high,
            start=f"{clone.index[0]:%Y-%m-%d}",
            end=f"{clone.index[-1]:%Y-%m-%d}",
            error="",
        )
    except Exception as exc:  # report the failure for this fund and carry on
        row["error"] = f"{type(exc).__name__}: {exc}"
    return row


def median_range(values, draws: int = 10_000, seed: int = 0) -> tuple[float, float]:
    """95% bootstrap range of the median: the funds are drawn with replacement and the
    2.5th and 97.5th percentiles of the resulting medians taken. With a few dozen funds the
    median itself is uncertain by a few tenths of a percentage point."""
    x = np.asarray(values, dtype=float)
    rng = np.random.default_rng(seed)
    medians = np.median(rng.choice(x, size=(draws, len(x)), replace=True), axis=1)
    return float(np.percentile(medians, 2.5)), float(np.percentile(medians, 97.5))


PASSIVE = ("Index", "Single stock")  # categories left out of the tally of active funds


def verdicts(ok: pd.DataFrame) -> str:
    """How the actively managed funds fared after all fees, against their clone and against
    the closest single ETF: how many came out ahead, and how many were ahead or behind by
    more than noise, meaning that the 95% range of the gap excludes zero."""
    active = ok[~ok["category"].isin(PASSIVE)]
    lines = [f"\n{len(active)} active funds, after all fees:"]
    for name, gap in (("clone", "gap"), ("closest single ETF", "gap_closest")):
        lines.append(
            f"  against the {name}: ahead {int((active[gap] > 0).sum())}, by more than noise "
            f"{int((active[f'{gap}_low'] > 0).sum())}; behind by more than noise "
            f"{int((active[f'{gap}_high'] < 0).sum())}; median gap {active[gap].median():+.2%}"
        )
    return "\n".join(lines)


def summarise(results: pd.DataFrame) -> str:
    ok = results[results["error"] == ""]
    lines = []
    for _, row in results[results["error"] != ""].iterrows():
        lines.append(f"FAILED {row['ticker']}: {row['error']}")
    columns = [
        *("tracking_error", "te_weekly", "te_monthly", "r2_weekly", "turnover", "holdings"),
        *("te_closest", "gap"),
    ]
    table = ok[["ticker", "category", *columns]]
    lines.append(table.to_string(index=False, float_format=lambda v: f"{v:.3f}"))
    by_category = ok.groupby("category")[["te_weekly", "r2_weekly"]].median()
    lines.append("\nMedian by category:\n" + by_category.to_string(float_format="{:.3f}".format))
    low, high = median_range(ok["te_weekly"])
    lines.append(
        f"\nfunds {len(ok)}/{len(results)} | median TE weekly {ok['te_weekly'].median():.4f} "
        f"(95% range {low:.4f} to {high:.4f}) | "
        f"mean TE weekly {ok['te_weekly'].mean():.4f} | median TE daily "
        f"{ok['tracking_error'].median():.4f} | median R² weekly {ok['r2_weekly'].median():.3f} | "
        f"median turnover {ok['turnover'].median():.2f} | "
        f"median holdings {ok['holdings'].median():.1f} | "
        f"median TE weekly of the closest single ETF {ok['te_closest'].median():.4f}"
    )
    lines.append(verdicts(ok))
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument(
        "--prices", default=DATA_DIR / "closes.parquet", help="parquet of adjusted closes"
    )
    parser.add_argument("--rf", default=DATA_DIR / "rf.csv", help="CSV of the daily T-bill rate")
    parser.add_argument(
        "--split", default="dev", help=f'"all" or a comma-separated list of: {", ".join(SPLITS)}'
    )
    parser.add_argument("--funds", help="comma-separated tickers; overrides --split")
    parser.add_argument(
        "--universe", default="all", help='"all", "legacy", "traded-by:DATE" or a comma list'
    )
    parser.add_argument(
        "--etf-set", type=str.upper, choices=list(etfs.SETS), default=etfs.DEFAULT_SET
    )
    parser.add_argument(
        "--eval-start", default=EVAL_START, help="first date scored (default 2010-01-04)"
    )
    parser.add_argument("--eval-end", help="last date scored (default: the end of the data)")
    parser.add_argument("--estimator", help="path/to/file.py:function")
    parser.add_argument("--window", type=int, default=252)
    parser.add_argument("--rebalance", choices=["M", "Q"], default="M")
    parser.add_argument("--frequency", choices=["daily", "weekly"], default="daily")
    parser.add_argument("--cost-bps", type=float, default=5.0)
    parser.add_argument("--max-etfs", type=int, help="cap on the number of ETFs")
    parser.add_argument("--min-weight", type=float, default=0.02, help="smallest position kept")
    parser.add_argument(
        "--overlap",
        type=int,
        default=ReplicationConfig().overlap,
        help="fit on overlapping n-day sums (default: the app's)",
    )
    parser.add_argument("--raw", action="store_true", help="keep stale fund prices")
    parser.add_argument("--jobs", type=int, default=8)
    parser.add_argument("--out", help="write per-fund results to this CSV")
    args = parser.parse_args(argv)

    funds = pd.read_csv(FUNDS_FILE)
    if args.funds:
        wanted = [ticker.strip().upper() for ticker in args.funds.split(",")]
        funds = funds[funds["ticker"].isin(wanted)]
    elif args.split != "all":
        splits = args.split.split(",")
        if unknown := sorted(set(splits) - set(SPLITS)):
            parser.error(f"unknown split {', '.join(unknown)}; choose from {', '.join(SPLITS)}")
        funds = funds[funds["split"].isin(splits)]
    if funds.empty:
        parser.error("no fund in funds.csv matches the selection")
    config = ReplicationConfig(
        window=args.window,
        rebalance=args.rebalance,
        frequency=args.frequency,
        cost_bps=args.cost_bps,
        max_etfs=args.max_etfs,
        min_weight=args.min_weight,
        overlap=args.overlap,
    )
    load_estimator(args.estimator)  # a bad path fails here, not in every worker
    records = funds.to_dict("records")
    initargs = (
        args.prices,
        args.rf,
        args.estimator,
        config,
        not args.raw,
        args.etf_set,
        args.eval_start,
        args.eval_end,
    )
    with ProcessPoolExecutor(args.jobs, initializer=_init, initargs=initargs) as pool:
        rows = list(pool.map(evaluate, records, [args.universe] * len(records)))
    results = pd.DataFrame(rows)
    if args.out:
        results.to_csv(args.out, index=False)
    print(summarise(results))


if __name__ == "__main__":
    main()
