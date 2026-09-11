"""Download the price snapshot the benchmark runs on.

    python -m benchmarks.download

Writes closes.parquet (adjusted daily closes, full history, of every ETF in
factorlens.etfs and every fund in funds.csv) and rf.csv (the daily one-month T-bill
rate from the Kenneth French data library) to benchmarks/data, or to --out. Yahoo
Finance revises history now and then, so a fresh snapshot can move the results slightly.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

from benchmarks.run import DATA_DIR, FUNDS_FILE
from factorlens import etfs
from factorlens.data import fetch_prices, load_french_factors


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--out", default=DATA_DIR, help="output directory")
    args = parser.parse_args(argv)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    tickers = [*etfs.tickers(), *pd.read_csv(FUNDS_FILE)["ticker"]]
    tomorrow = (pd.Timestamp.today() + pd.Timedelta(days=1)).strftime("%Y-%m-%d")
    prices = fetch_prices(tickers, "1990-01-01", tomorrow)
    prices.to_parquet(out / "closes.parquet")
    load_french_factors("US", "daily")["RF"].to_csv(out / "rf.csv")

    missing = sorted(set(tickers) - set(prices.columns))
    print(f"{prices.shape[1]} series, {prices.index[0]:%Y-%m-%d} to {prices.index[-1]:%Y-%m-%d}")
    if missing:
        print(f"no data for: {', '.join(missing)}")


if __name__ == "__main__":
    main()
