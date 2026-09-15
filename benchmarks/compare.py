"""Compare two benchmark runs fund by fund.

    python -m benchmarks.run --split all --universe legacy --raw --out before.csv
    python -m benchmarks.run --split all --window 378 --estimator product --out after.csv
    python -m benchmarks.compare before.csv after.csv --split fresh

For the funds that both runs scored, the weekly tracking error of the first run minus that
of the second is taken fund by fund. Its median comes with a 95% bootstrap range over the
funds: the "fund by fund" figures in the README.
"""

from __future__ import annotations

import argparse

import pandas as pd

from benchmarks.run import SPLITS, median_range


def paired(
    first: pd.DataFrame,
    second: pd.DataFrame,
    column: str = "te_weekly",
    second_column: str | None = None,
) -> dict:
    """The fund-by-fund difference of `column` in the first run minus `second_column` (by
    default the same column) in the second, over the funds both runs scored: its median
    with a 95% bootstrap range, and on how many funds it is positive."""

    def scored(results: pd.DataFrame, name: str) -> pd.Series:
        ok = results[results["error"].fillna("") == ""]
        return ok.set_index("ticker")[name]

    a, b = scored(first, column), scored(second, second_column or column)
    both = a.index.intersection(b.index)
    if both.empty:
        raise ValueError("the two runs have no fund in common")
    difference = a[both] - b[both]
    low, high = median_range(difference)
    return {
        "funds": len(difference),
        "median": float(difference.median()),
        "low": low,
        "high": high,
        "positive": int((difference > 0).sum()),
    }


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("first", help="per-fund CSV of a benchmark run (benchmarks.run --out)")
    parser.add_argument("second", help="per-fund CSV of another run")
    parser.add_argument(
        "--split", default="all", help=f'"all" or a comma-separated list of: {", ".join(SPLITS)}'
    )
    parser.add_argument("--column", default="te_weekly", help="the figure to compare")
    parser.add_argument(
        "--second-column", help="the figure of the second run, if not the same, e.g. te_closest"
    )
    args = parser.parse_args(argv)

    first, second = pd.read_csv(args.first), pd.read_csv(args.second)
    if args.split != "all":
        splits = args.split.split(",")
        if unknown := sorted(set(splits) - set(SPLITS)):
            parser.error(f"unknown split {', '.join(unknown)}; choose from {', '.join(SPLITS)}")
        first = first[first["split"].isin(splits)]
    try:
        result = paired(first, second, args.column, args.second_column)
    except (KeyError, ValueError) as exc:
        parser.error(str(exc))
    names = args.column + (f" minus {args.second_column}" if args.second_column else "")
    print(
        f"{result['funds']} funds | {names}, first minus second: median "
        f"{result['median']:+.4f} (95% range {result['low']:+.4f} to {result['high']:+.4f}) | "
        f"positive on {result['positive']}"
    )


if __name__ == "__main__":
    main()
