"""Command line: clone a fund or a portfolio with ETFs and print the result."""

from __future__ import annotations

import argparse
import datetime as dt
import logging
import re

import pandas as pd

from fundclone import __version__, etfs
from fundclone.analysis import run_analysis
from fundclone.attribution import FACTOR_NAMES
from fundclone.data import REGIONS
from fundclone.portfolio import parse_portfolio
from fundclone.replication import ReplicationConfig
from fundclone.report import headline


def looks_like_portfolio(text: str) -> bool:
    """True for "VTI 60, BND 40" and similar, False for a single ticker such as EXS1.DE."""
    return bool(re.search(r"[\s,;:]\s*\d", text.strip()))


def _date(text: str) -> str:
    try:
        return dt.date.fromisoformat(text).isoformat()
    except ValueError:
        raise argparse.ArgumentTypeError(f"not a date of the form YYYY-MM-DD: {text!r}") from None


def _positive(text: str) -> int:
    if not text.isdigit() or int(text) < 1:
        raise argparse.ArgumentTypeError(f"not a whole number of at least 1: {text!r}")
    return int(text)


def _fee(text: str) -> float:
    """A yearly fee in percent, returned as a decimal."""
    try:
        value = float(text)
    except ValueError:
        value = float("nan")
    if not 0 <= value < 10:
        raise argparse.ArgumentTypeError(f"not a percentage between 0 and 10: {text!r}")
    return value / 100


def _asset_classes(
    parser: argparse.ArgumentParser, text: str | None, etf_set: str = etfs.DEFAULT_SET
) -> list[str] | None:
    """Asset-class names of a set from a comma-separated list, matched regardless of case."""
    if not text:
        return None
    offered = etfs.asset_classes(etf_set)
    known = {name.lower(): name for name in offered}
    chosen = []
    for name in (part.strip() for part in text.split(",")):
        if name.lower() not in known:
            parser.error(f"unknown asset class {name!r}; choose from: {', '.join(offered)}")
        chosen.append(known[name.lower()])
    return chosen


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        prog="fundclone",
        description="Clone a fund or a portfolio with ETFs and explain it with factors.",
    )
    parser.add_argument("--version", action="version", version=f"fundclone {__version__}")
    parser.add_argument(
        "target", help='a Yahoo Finance ticker such as DODGX, or a portfolio: "VTI 60, BND 40"'
    )
    parser.add_argument(
        "--start", type=_date, default="2005-01-01", help="first date (default 2005-01-01)"
    )
    parser.add_argument(
        "--end", type=_date, default=dt.date.today().isoformat(), help="last date (default today)"
    )
    parser.add_argument("--max-etfs", type=_positive, help="cap on the number of ETFs in the clone")
    parser.add_argument(
        "--expense-ratio",
        type=_fee,
        help="the fund's expense ratio in percent, if Yahoo Finance reports none, e.g. 1.5",
    )
    parser.add_argument(
        "--etf-set",
        type=str.upper,
        choices=list(etfs.SETS),
        default=etfs.DEFAULT_SET,
        help="the set of ETFs the clone is built from (default: US)",
    )
    parser.add_argument(
        "--asset-classes",
        help="comma-separated groups of the ETF set, for the US set: "
        + ", ".join(etfs.ASSET_CLASSES),
    )
    parser.add_argument("--window", type=int, default=378, help="estimation window, trading days")
    parser.add_argument("--rebalance", choices=["M", "Q"], default="M")
    parser.add_argument(
        "--fit-on",
        choices=["auto", "daily", "weekly"],
        default="auto",
        help="returns the clone is fitted to (auto: weekly if anything is priced outside US hours)",
    )
    parser.add_argument("--frequency", choices=["monthly", "daily"], default="monthly")
    parser.add_argument("--region", choices=REGIONS, help="factor region (default: automatic)")
    args = parser.parse_args(argv)
    if args.start >= args.end:
        parser.error("--start must come before --end")
    classes = _asset_classes(parser, args.asset_classes, args.etf_set)
    # yfinance's 404 messages repeat ours. Keep them off the terminal without raising the
    # logger's level: fundclone.data reads them to notice when Yahoo limits requests.
    yahoo = logging.getLogger("yfinance")
    yahoo.addHandler(logging.NullHandler())
    yahoo.propagate = False

    try:
        target = parse_portfolio(args.target) if looks_like_portfolio(args.target) else args.target
        config = ReplicationConfig(
            window=args.window,
            rebalance=args.rebalance,
            frequency=args.fit_on,
            max_etfs=args.max_etfs,
        )
        a = run_analysis(
            target,
            args.start,
            args.end,
            replication=config,
            asset_classes=classes,
            frequency=args.frequency,
            region=args.region,
            etf_set=args.etf_set,
            expense_ratio=args.expense_ratio,
        )
    except ValueError as exc:  # bad tickers, portfolios, settings and too-short histories
        parser.exit(1, f"fundclone: {exc}\n")

    returns = a.returns
    title = a.name if a.holdings else f"{a.name} ({a.label})"
    print(f"{title}, out of sample {returns.index[0]:%Y-%m-%d} to {returns.index[-1]:%Y-%m-%d}\n")
    for line in headline(a):
        print(line)

    allocation = a.allocation()
    print(f"\nClone as of {a.replication.weights.index[-1]:%Y-%m-%d}:")
    ticker_width = max(6, int(allocation["ETF"].str.len().max()))
    name_width = max(34, int(allocation["Name"].str.len().max()))
    for _, row in allocation.iterrows():
        line = f"  {row['ETF']:<{ticker_width}} {row['Name']:<{name_width}} {row['Weight']:>7.1%}"
        print(f"{line}  {row['ISIN']}".rstrip() if "ISIN" in allocation else line)

    perf = a.performance.copy()
    for column in ["annual_return", "volatility", "max_drawdown", "total_return"]:
        perf[column] = perf[column].map(lambda v: "–" if pd.isna(v) else f"{v:.1%}")
    perf["sharpe"] = perf["sharpe"].map("{:.2f}".format)
    print("\n" + perf.to_string())

    att = a.attribution
    if att is not None:
        print(
            f"\nFactor exposures ({att.n_obs} {a.frequency} returns, {att.start:%Y-%m} to "
            f"{att.end:%Y-%m}, {a.region} factors):"
        )
        table = att.table().drop(columns="Factor").rename(index=FACTOR_NAMES)
        table["Contribution p.a."] = table["Contribution p.a."].map("{:.2%}".format)
        with pd.option_context("display.float_format", "{:.2f}".format):
            print(table.to_string(na_rep=""))
    for note in a.notes:
        print(f"note: {note}")


if __name__ == "__main__":
    main()
