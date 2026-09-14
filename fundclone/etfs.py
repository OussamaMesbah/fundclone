"""The liquid ETFs a clone can be built from, with their annual expense ratios.

There is one set of US-listed ETFs, the default, and each ETF belongs to an asset class
(a group of building blocks). Group names are unique across sets.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

import pandas as pd

# US set: net expense ratios as reported by Yahoo Finance. UCITS set: total expense ratios
# from justETF, read on 14 September 2026.
EXPENSE_RATIOS_AS_OF = "September 2026"
DEFAULT_SET = "US"
UCITS = "UCITS"
SETS: dict[str, str] = {  # set -> what its ETFs are
    DEFAULT_SET: "liquid US-listed ETFs",
    UCITS: "UCITS ETFs on Xetra, which investors in the EU can buy",
}


@dataclass(frozen=True)
class ETF:
    ticker: str
    name: str
    asset_class: str
    expense_ratio: float  # annual, as a decimal
    currency: str = "USD"  # of its quote on Yahoo Finance
    etf_set: str = DEFAULT_SET
    isin: str = ""  # for the UCITS set, where investors buy by ISIN


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

# UCITS ETFs (and one gold ETC) listed on Xetra and quoted in EUR, which investors in the
# EU can buy where US-listed ETFs are not offered to them. Each was checked for a clean
# price history on Yahoo Finance; ISINs and TERs are from justETF (14 September 2026).
# asset class -> ticker -> (name, total expense ratio in percent, ISIN)
_UCITS_TABLE: dict[str, dict[str, tuple[str, float, str]]] = {
    "World equity": {
        "EUNL.DE": ("MSCI World", 0.20, "IE00B4L5Y983"),
        "IUSN.DE": ("MSCI World Small Cap", 0.35, "IE00BF4RFH31"),
    },
    "US equity (UCITS)": {
        "SXR8.DE": ("S&P 500", 0.07, "IE00B5BMR087"),
        "SXRV.DE": ("Nasdaq-100", 0.30, "IE00B53SZB19"),
        "ZPRR.DE": ("Russell 2000", 0.30, "IE00BJ38QD84"),
        "QDVI.DE": ("MSCI USA Value", 0.20, "IE00BD1F4M44"),
    },
    "European equity": {
        "EXSA.DE": ("STOXX Europe 600", 0.20, "DE0002635307"),
        "EXW1.DE": ("EURO STOXX 50", 0.09, "DE0005933956"),
        "EXSE.DE": ("STOXX Europe Small 200", 0.20, "DE000A0D8QZ7"),
        "IUSZ.DE": ("FTSE 100", 0.07, "IE0005042456"),
    },
    "Asia-Pacific equity": {
        "EUNN.DE": ("MSCI Japan IMI", 0.12, "IE00B4L5YX21"),
        "SXR1.DE": ("MSCI Pacific ex Japan", 0.20, "IE00B52MJY50"),
    },
    "Emerging markets (UCITS)": {
        "IS3N.DE": ("MSCI Emerging Markets IMI", 0.18, "IE00BKM4GZ66"),
        "CEBL.DE": ("MSCI EM Asia", 0.20, "IE00B5L8K969"),
        "XCS6.DE": ("MSCI China", 0.65, "LU0514695690"),
        "QDV5.DE": ("MSCI India", 0.65, "IE00BZCQB185"),
    },
    "World factors": {
        "IS3Q.DE": ("MSCI World Quality", 0.25, "IE00BP3QZ601"),
        "IS3R.DE": ("MSCI World Momentum", 0.25, "IE00BP3QZ825"),
        "IS3S.DE": ("MSCI World Value", 0.25, "IE00BP3QZB59"),
        "IQQ0.DE": ("MSCI World Minimum Volatility", 0.30, "IE00B8FHGS14"),
        "ISPA.DE": ("STOXX Global Select Dividend 100", 0.46, "DE000A0F5UH1"),
    },
    "World sectors": {
        "XDWT.DE": ("MSCI World Information Technology", 0.25, "IE00BM67HT60"),
        "XDWH.DE": ("MSCI World Health Care", 0.25, "IE00BM67HK77"),
        "XDWF.DE": ("MSCI World Financials", 0.25, "IE00BM67HL84"),
        "XDW0.DE": ("MSCI World Energy", 0.25, "IE00BM67HM91"),
        "XDWI.DE": ("MSCI World Industrials", 0.25, "IE00BM67HV82"),
        "XDWC.DE": ("MSCI World Consumer Discretionary", 0.25, "IE00BM67HP23"),
        "XDWS.DE": ("MSCI World Consumer Staples", 0.25, "IE00BM67HN09"),
        "XDWU.DE": ("MSCI World Utilities", 0.25, "IE00BM67HQ30"),
        "XDWM.DE": ("MSCI World Materials", 0.25, "IE00BM67HS53"),
        "XWTS.DE": ("MSCI World Communication Services", 0.25, "IE00BM67HR47"),
    },
    "EUR bonds": {
        "EUNH.DE": ("Euro government bonds", 0.07, "IE00B4WXJJ64"),
        "DBXP.DE": ("Euro government bonds 1-3y", 0.10, "LU0290356871"),
        "IBCL.DE": ("Euro government bonds 15-30y", 0.15, "IE00B1FZS913"),
        "IBCI.DE": ("Euro inflation-linked government bonds", 0.09, "IE00B0M62X26"),
        "EUN5.DE": ("EUR corporate bonds", 0.09, "IE00B3F81R35"),
        "EUNW.DE": ("EUR high-yield corporates", 0.50, "IE00B66F4759"),
        "IS3M.DE": ("EUR ultrashort bonds", 0.09, "IE00BCRY6557"),
        "XEON.DE": ("EUR overnight rate", 0.10, "LU0290358497"),
    },
    "Global bonds": {
        "EUNA.DE": ("Global aggregate bonds, EUR hedged", 0.10, "IE00BDBRDM35"),
        "IUSM.DE": ("7-10y US Treasuries", 0.07, "IE00B1FZS798"),
        "IS04.DE": ("20+y US Treasuries", 0.07, "IE00BSKRJZ44"),
        "IBCD.DE": ("USD corporate bonds", 0.20, "IE0032895942"),
        "IUS7.DE": ("Emerging-market USD bonds", 0.45, "IE00B2NPKV68"),
    },
    "Real assets (UCITS)": {
        # Xetra-Gold takes no fee from its price; the bank may charge for custody.
        "4GLD.DE": ("Gold (Xetra-Gold, an ETC)", 0.0, "DE000A0S9GB0"),
        "EXXY.DE": ("Diversified commodities", 0.46, "DE000A0H0728"),
        "IQQ6.DE": ("Developed-market property", 0.59, "IE00B1FZS350"),
    },
}

# Known errors in Yahoo Finance's Xetra prices, found by scanning every series for moves
# that reverse or break away from related ETFs, and left out by without_known_errors:
# prices before a start date (stale or mis-scaled quotes after the listing), and single
# days that jump and reverse the next day while the market barely moves.
DATA_FROM: dict[str, str] = {
    "EUNL.DE": "2009-10-21",  # unchanged for 17 days after the listing
    "SXR8.DE": "2010-11-01",  # stale, then about 25% too high until 29 October 2010
    "SXRV.DE": "2010-11-01",  # about 28% too high until 29 October 2010
    "SXR1.DE": "2010-11-01",  # about 27% too high until 29 October 2010
    "IQQ0.DE": "2013-05-02",  # swings of 25-30% that reverse, February to April 2013
    "IS3Q.DE": "2015-01-02",  # swings of 20-30% that reverse, October to December 2014
    "IS3R.DE": "2015-01-02",
    "IS3S.DE": "2015-01-02",
    "XDW0.DE": "2017-04-19",  # no prices for the 47 days before
}
BAD_DAYS: dict[str, tuple[str, ...]] = {
    # up 13-16% with the MSCI World flat, and back the next trading day
    "IS3Q.DE": ("2017-06-05",),
    "IS3R.DE": ("2015-05-08", "2017-06-05"),
    "IS3S.DE": ("2017-06-05",),
    "IQQ0.DE": ("2017-06-05", "2025-10-24"),
}


def without_known_errors(prices: pd.DataFrame) -> pd.DataFrame:
    """The prices with the known errors of DATA_FROM and BAD_DAYS set to missing."""
    fixed = prices.copy()
    for ticker, start in DATA_FROM.items():
        if ticker in fixed:
            fixed.loc[fixed.index < pd.Timestamp(start), ticker] = float("nan")
    for ticker, days in BAD_DAYS.items():
        if ticker in fixed:
            fixed.loc[fixed.index.isin(pd.to_datetime(list(days))), ticker] = float("nan")
    return fixed


# The share of US stocks in each equity group, which sets the region of the factor model.
# Groups without an entry hold no equity. World groups count at about the US weight of
# the MSCI World, some 70%.
US_SHARE: dict[str, float] = {
    "US equity": 1.0,
    "US sectors": 1.0,
    "US industries": 1.0,
    "US factors": 1.0,
    "International equity": 0.0,
    "Emerging markets": 0.0,
    "World equity": 0.7,
    "US equity (UCITS)": 1.0,
    "European equity": 0.0,
    "Asia-Pacific equity": 0.0,
    "Emerging markets (UCITS)": 0.0,
    "World factors": 0.7,
    "World sectors": 0.7,
}

ETFS: list[ETF] = [
    ETF(ticker, name, asset_class, pct / 100)
    for asset_class, members in _TABLE.items()
    for ticker, (name, pct) in members.items()
] + [
    ETF(ticker, name, asset_class, pct / 100, "EUR", UCITS, isin)
    for asset_class, members in _UCITS_TABLE.items()
    for ticker, (name, pct, isin) in members.items()
]
BY_TICKER: dict[str, ETF] = {etf.ticker: etf for etf in ETFS}


def asset_classes(etf_set: str = DEFAULT_SET) -> list[str]:
    """The groups of building blocks in one set of ETFs, in catalogue order."""
    return list(dict.fromkeys(etf.asset_class for etf in ETFS if etf.etf_set == etf_set))


ASSET_CLASSES = asset_classes()  # those of the default set


def tickers(classes: list[str] | None = None, etf_set: str = DEFAULT_SET) -> list[str]:
    """ETF tickers of some asset classes, or of every class in `etf_set`."""
    if classes is None:
        return [etf.ticker for etf in ETFS if etf.etf_set == etf_set]
    return [etf.ticker for etf in ETFS if etf.asset_class in classes]


def equity_weight(class_weights: Mapping[str, float]) -> float:
    """Total weight of the equity groups in weights by asset class."""
    return sum(weight for name, weight in class_weights.items() if name in US_SHARE)


def international_weight(class_weights: Mapping[str, float]) -> float:
    """Weight of non-US stocks in weights by asset class: a world group counts in part."""
    return sum(
        weight * (1 - US_SHARE[name]) for name, weight in class_weights.items() if name in US_SHARE
    )


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
