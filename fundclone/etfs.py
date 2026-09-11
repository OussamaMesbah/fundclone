"""The liquid US-listed ETFs a clone can be built from, with their annual expense ratios."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

EXPENSE_RATIOS_AS_OF = "September 2026"  # net expense ratios as reported by Yahoo Finance


@dataclass(frozen=True)
class ETF:
    ticker: str
    name: str
    asset_class: str
    expense_ratio: float  # annual, as a decimal


# asset class -> ticker -> (name, net expense ratio in percent)
_TABLE: dict[str, dict[str, tuple[str, float]]] = {
    "US equity": {
        "SPY": ("S&P 500", 0.0945),
        "QQQ": ("Nasdaq-100", 0.18),
        "IWD": ("Russell 1000 Value", 0.18),
        "IWF": ("Russell 1000 Growth", 0.18),
        "IJH": ("S&P MidCap 400", 0.05),
        "IWS": ("Russell Midcap Value", 0.23),
        "IWP": ("Russell Midcap Growth", 0.23),
        "IWM": ("Russell 2000", 0.19),
        "IWN": ("Russell 2000 Value", 0.24),
        "IWO": ("Russell 2000 Growth", 0.24),
        "DVY": ("Dow Jones Select Dividend", 0.38),
        "VIG": ("Dividend Appreciation", 0.04),
    },
    "US sectors": {
        "XLK": ("Technology", 0.08),
        "XLF": ("Financials", 0.08),
        "XLV": ("Health Care", 0.08),
        "XLE": ("Energy", 0.08),
        "XLI": ("Industrials", 0.08),
        "XLY": ("Consumer Discretionary", 0.08),
        "XLP": ("Consumer Staples", 0.08),
        "XLU": ("Utilities", 0.08),
        "XLB": ("Materials", 0.08),
        "XLRE": ("Real Estate", 0.08),
        "XLC": ("Communication Services", 0.08),
    },
    "US industries": {
        "SOXX": ("Semiconductors", 0.33),
        "IGV": ("Software", 0.38),
        "FDN": ("Internet", 0.49),
        "IBB": ("Biotechnology", 0.44),
        "XBI": ("Biotechnology, equal weight", 0.35),
        "IHE": ("Pharmaceuticals", 0.37),
        "IHI": ("Medical devices", 0.37),
        "KRE": ("Regional banks", 0.35),
        "KIE": ("Insurance", 0.35),
        "ITA": ("Aerospace & defense", 0.37),
        "IYT": ("Transportation", 0.37),
        "XHB": ("Homebuilders", 0.35),
        "XRT": ("Retail", 0.35),
        "XOP": ("Oil & gas exploration", 0.35),
        "GDX": ("Gold miners", 0.51),
        "ICLN": ("Clean energy", 0.38),
    },
    "US factors": {
        "MTUM": ("MSCI USA Momentum", 0.15),
        "QUAL": ("MSCI USA Quality", 0.15),
        "USMV": ("MSCI USA Minimum Volatility", 0.15),
        "VLUE": ("MSCI USA Value", 0.15),
    },
    "International equity": {
        "EFA": ("MSCI EAFE", 0.32),
        "EFV": ("MSCI EAFE Value", 0.31),
        "EFG": ("MSCI EAFE Growth", 0.34),
        "SCZ": ("MSCI EAFE Small-Cap", 0.40),
        "EZU": ("MSCI EMU", 0.50),
        "EWU": ("MSCI United Kingdom", 0.50),
        "EWJ": ("MSCI Japan", 0.49),
        "EWC": ("MSCI Canada", 0.50),
        "EWL": ("MSCI Switzerland", 0.50),
        "EWA": ("MSCI Australia", 0.50),
    },
    "Emerging markets": {
        "EEM": ("MSCI Emerging Markets", 0.72),
        "AAXJ": ("MSCI All Country Asia ex Japan", 0.72),
        "FXI": ("China Large-Cap", 0.73),
        "EWZ": ("MSCI Brazil", 0.59),
        "EWY": ("MSCI South Korea", 0.59),
        "EWT": ("MSCI Taiwan", 0.59),
        "INDA": ("MSCI India", 0.61),
    },
    "Bonds": {
        "SHY": ("1-3y Treasuries", 0.15),
        "IEI": ("3-7y Treasuries", 0.15),
        "IEF": ("7-10y Treasuries", 0.15),
        "TLT": ("20+y Treasuries", 0.15),
        "TIP": ("TIPS", 0.18),
        "AGG": ("US Aggregate", 0.03),
        "MBB": ("Mortgage-backed", 0.04),
        "VCSH": ("Short-term corporates", 0.03),
        "VCIT": ("Intermediate corporates", 0.03),
        "LQD": ("Investment-grade corporates", 0.14),
        "FLOT": ("Floating-rate notes", 0.15),
        "HYG": ("High-yield corporates", 0.49),
        "BKLN": ("Senior loans", 0.65),
        "CWB": ("Convertible bonds", 0.40),
        "MUB": ("Municipal bonds", 0.05),
        "EMB": ("Emerging-market USD bonds", 0.39),
        "BWX": ("International Treasuries", 0.35),
        "BNDX": ("International bonds, USD hedged", 0.07),
    },
    "Real assets": {
        "VNQ": ("US REITs", 0.13),
        "GLD": ("Gold", 0.40),
        "DBC": ("Commodities", 0.85),
    },
}

ASSET_CLASSES = list(_TABLE)
EQUITY_CLASSES = ["US equity", "US sectors", "US industries", "US factors"]
INTERNATIONAL_CLASSES = ["International equity", "Emerging markets"]

ETFS: list[ETF] = [
    ETF(ticker, name, asset_class, pct / 100)
    for asset_class, members in _TABLE.items()
    for ticker, (name, pct) in members.items()
]
BY_TICKER: dict[str, ETF] = {etf.ticker: etf for etf in ETFS}


def tickers(asset_classes: list[str] | None = None) -> list[str]:
    """ETF tickers, optionally restricted to some asset classes."""
    return [etf.ticker for etf in ETFS if asset_classes is None or etf.asset_class in asset_classes]


def expense_ratio(weights: Mapping[str, float]) -> float:
    """Annual expense ratio of an ETF allocation; the cash part costs nothing."""
    return float(sum(w * BY_TICKER[t].expense_ratio for t, w in weights.items() if t in BY_TICKER))


def asset_class_weights(weights: Mapping[str, float]) -> dict[str, float]:
    """Total weight per asset class of an ETF allocation."""
    totals: dict[str, float] = {}
    for ticker, weight in weights.items():
        asset_class = BY_TICKER[ticker].asset_class if ticker in BY_TICKER else "Other"
        totals[asset_class] = totals.get(asset_class, 0.0) + weight
    return totals
