"""Download the price snapshot the benchmark runs on.

    python -m benchmarks.download

Writes closes.parquet (adjusted daily closes, full history, of every ETF in
fundclone.etfs and every fund in funds.csv) and rf.csv (the daily one-month T-bill
rate from the Kenneth French data library) to benchmarks/data, or to --out. Yahoo
Finance revises history now and then, so a fresh snapshot can move the results slightly.

    python -m benchmarks.download --snapshot data/prices.parquet

also writes the compact copy the web app falls back on when Yahoo Finance does not answer:
the same prices since 2004, as 32-bit floats.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

from benchmarks.run import DATA_DIR, FUNDS_FILE
from fundclone import etfs
from fundclone.data import fetch_prices, load_french_factors

SNAPSHOT_START = "2004-01-01"


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--out", default=DATA_DIR, help="output directory")
    parser.add_argument("--snapshot", help="also write the web app's price snapshot here")
    args = parser.parse_args(argv)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    tickers = [*etfs.tickers(), *pd.read_csv(FUNDS_FILE)["ticker"]]
    tomorrow = (pd.Timestamp.today() + pd.Timedelta(days=1)).strftime("%Y-%m-%d")
    prices = fetch_prices(tickers, "1990-01-01", tomorrow)
    prices.to_parquet(out / "closes.parquet")
    load_french_factors("US", "daily")["RF"].to_csv(out / "rf.csv")

    if args.snapshot:
        compact = prices.loc[prices.index >= SNAPSHOT_START].astype("float32")
        compact.to_parquet(args.snapshot, compression="zstd")
        print(f"app snapshot: {compact.shape[1]} series from {compact.index[0]:%Y-%m-%d}")

    missing = sorted(set(tickers) - set(prices.columns))
    print(f"{prices.shape[1]} series, {prices.index[0]:%Y-%m-%d} to {prices.index[-1]:%Y-%m-%d}")
    if missing:
        print(f"no data for: {', '.join(missing)}")


if __name__ == "__main__":
    main()
