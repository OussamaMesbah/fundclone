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
        "VLUE": ("MSCI USA Enhanced Value", 0.15),
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
        "QDVI.DE": ("MSCI USA Enhanced Value", 0.20, "IE00BD1F4M44"),
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


@dataclass(frozen=True)
class Twin:
    """A UCITS ETF, or for gold an ETC, that an investor in the EU can buy in place of a
    US-listed ETF of the default set."""

    name: str
    expense_ratio: float  # annual total expense ratio, as a decimal
    isin: str
    match: str  # "same" index, "capped" (the same index, capped differently) or "similar"
    index: str  # the index the twin follows
    note: str = ""

    def describe(self) -> str:
        """How the twin's index relates to the US-listed ETF's, and anything else to know."""
        text = {
            "same": "Same index",
            "capped": f"Same index, capped differently ({self.index})",
            "similar": f"Similar index: {self.index}",
        }[self.match]
        return f"{text}; {self.note}" if self.note else text


# UCITS twins of the US-listed ETFs, with names, total expense ratios, ISINs and indices
# from justETF, read on 15 September 2026. 64 of the 81 have one. There is none for Russell
# midcap value and growth, small-cap growth, eight US industries, EAFE value, growth and
# small caps, senior loans and municipal bonds.
TWINS_AS_OF = "15 September 2026"
# US ticker -> (name, total expense ratio in percent, ISIN, match, index[, note])
_TWIN_TABLE: dict[str, tuple] = {
    "SPY": ("iShares Core S&P 500 UCITS ETF USD (Acc)", 0.07, "IE00B5BMR087", "same", "S&P 500"),
    "QQQ": ("iShares Nasdaq 100 UCITS ETF (Acc)", 0.3, "IE00B53SZB19", "same", "Nasdaq 100"),
    "IWD": (
        "Vanguard Russell 1000 U.S. Value UCITS ETF USD Acc",
        0.16,
        "IE000US24HF4",
        "same",
        "Russell 1000 Value",
        "launched in July 2026",
    ),
    "IWF": (
        "Amundi Russell 1000 Growth UCITS ETF Acc",
        0.19,
        "IE0005E8B9S4",
        "same",
        "Russell 1000 Growth",
    ),
    "IJH": (
        "State Street SPDR S&P 400 U.S. Mid Cap UCITS ETF USD Unhedged (Acc)",
        0.3,
        "IE00B4YBJ215",
        "same",
        "S&P MidCap 400",
    ),
    "IWM": (
        "State Street SPDR Russell 2000 U.S. Small Cap UCITS ETF USD",
        0.3,
        "IE00BJ38QD84",
        "same",
        "Russell 2000",
    ),
    "IWN": (
        "State Street SPDR MSCI USA Small Cap Value Weighted UCITS ETF USD",
        0.3,
        "IE00BSPLC413",
        "similar",
        "MSCI USA Small Cap Value Weighted",
    ),
    "DVY": (
        "iShares Dow Jones US Select Dividend UCITS ETF (DE)",
        0.31,
        "DE000A0D8Q49",
        "same",
        "Dow Jones US Select Dividend",
    ),
    "VIG": (
        "WisdomTree US Quality Dividend Growth UCITS ETF USD Acc",
        0.33,
        "IE00BZ56RG20",
        "similar",
        "WisdomTree US Quality Dividend Growth",
    ),
    "XLK": (
        "State Street SPDR S&P U.S. Technology Select Sector UCITS ETF USD",
        0.15,
        "IE00BWBXM948",
        "capped",
        "S&P Technology Select Sector Daily Capped 35/20",
    ),
    "XLF": (
        "State Street SPDR S&P U.S. Financials Select Sector UCITS ETF USD",
        0.15,
        "IE00BWBXM500",
        "capped",
        "S&P Financials Select Sector Daily Capped 35/20",
    ),
    "XLV": (
        "State Street SPDR S&P U.S. Health Care Select Sector UCITS ETF USD",
        0.15,
        "IE00BWBXM617",
        "capped",
        "S&P Health Care Select Sector Daily Capped 35/20",
    ),
    "XLE": (
        "State Street SPDR S&P U.S. Energy Select Sector UCITS ETF USD",
        0.15,
        "IE00BWBXM492",
        "capped",
        "S&P Energy Select Sector Daily Capped 35/20",
    ),
    "XLI": (
        "State Street SPDR S&P U.S. Industrials Select Sector UCITS ETF USD",
        0.15,
        "IE00BWBXM724",
        "capped",
        "S&P Industrial Select Sector Daily Capped 35/20",
    ),
    "XLY": (
        "State Street SPDR S&P U.S. Consumer Discretionary Select Sector UCITS ETF USD",
        0.15,
        "IE00BWBXM278",
        "capped",
        "S&P Consumer Discretionary Select Sector Daily Capped 35/20",
    ),
    "XLP": (
        "State Street SPDR S&P U.S. Consumer Staples Select Sector UCITS ETF USD",
        0.15,
        "IE00BWBXM385",
        "capped",
        "S&P Consumer Staples Select Sector Daily Capped 35/20",
    ),
    "XLU": (
        "State Street SPDR S&P U.S. Utilities Select Sector UCITS ETF USD",
        0.15,
        "IE00BWBXMB69",
        "capped",
        "S&P Utilities Select Sector Daily Capped 35/20",
    ),
    "XLB": (
        "State Street SPDR S&P U.S. Materials Select Sector UCITS ETF USD",
        0.15,
        "IE00BWBXM831",
        "capped",
        "S&P Materials Select Sector Daily Capped 35/20",
    ),
    "XLRE": (
        "Invesco US Real Estate Sector UCITS ETF",
        0.14,
        "IE00BYM8JD58",
        "capped",
        "S&P Select Sector Capped 20% Real Estate",
        "not on Xetra; on gettex and Borsa Italiana",
    ),
    "XLC": (
        "State Street SPDR S&P U.S. Communication Services Select Sector UCITS ETF USD",
        0.15,
        "IE00BFWFPX50",
        "capped",
        "S&P Communication Services Select Sector Daily Capped 35/20",
    ),
    "SOXX": (
        "VanEck Semiconductor UCITS ETF",
        0.35,
        "IE00BMC38736",
        "similar",
        "MarketVector US Listed Semiconductor 10% Capped Screened",
    ),
    "FDN": (
        "First Trust Dow Jones Internet UCITS ETF Acc",
        0.55,
        "IE00BG0SSC32",
        "same",
        "Dow Jones Internet Composite",
        "not on Xetra; on gettex and Euronext Amsterdam",
    ),
    "IBB": (
        "iShares Nasdaq US Biotechnology UCITS ETF",
        0.35,
        "IE00BYXG2H39",
        "similar",
        "Nasdaq Biotechnology",
    ),
    "ITA": (
        "iShares U.S. Aerospace & Defence UCITS ETF USD (Acc)",
        0.38,
        "IE000IR2DEM6",
        "capped",
        "Dow Jones U.S. Select Aerospace & Defense Capped 35/20",
        "launched in May 2026",
    ),
    "XOP": (
        "iShares Oil & Gas Exploration & Production UCITS ETF",
        0.55,
        "IE00B6R51Z18",
        "similar",
        "S&P Commodity Producers Oil & Gas Exploration & Production",
    ),
    "GDX": (
        "VanEck Gold Miners UCITS ETF",
        0.53,
        "IE00BQQP9F84",
        "same",
        "MarketVector Global Gold Miners",
    ),
    "ICLN": (
        "iShares Global Clean Energy Transition UCITS ETF USD (Dist)",
        0.65,
        "IE00B1XNHC34",
        "same",
        "S&P Global Clean Energy Transition",
    ),
    "MTUM": (
        "iShares Edge MSCI USA Momentum Factor UCITS ETF",
        0.2,
        "IE00BD1F4N50",
        "similar",
        "MSCI USA Momentum",
    ),
    "QUAL": (
        "iShares Edge MSCI USA Quality Factor UCITS ETF",
        0.2,
        "IE00BD1F4L37",
        "same",
        "MSCI USA Sector Neutral Quality",
    ),
    "USMV": (
        "Amundi MSCI USA Minimum Volatility Factor UCITS ETF DR",
        0.18,
        "LU1589349734",
        "same",
        "MSCI USA Minimum Volatility",
    ),
    "VLUE": (
        "iShares Edge MSCI USA Value Factor UCITS ETF",
        0.2,
        "IE00BD1F4M44",
        "same",
        "MSCI USA Enhanced Value",
    ),
    "EFA": (
        "Xtrackers MSCI World ex USA UCITS ETF 1C",
        0.15,
        "IE0006WW1TQ4",
        "similar",
        "MSCI World ex USA",
    ),
    "EZU": ("iShares Core MSCI EMU UCITS ETF EUR (Acc)", 0.12, "IE00B53QG562", "same", "MSCI EMU"),
    "EWU": ("iShares MSCI UK UCITS ETF (Acc)", 0.33, "IE00B539F030", "same", "MSCI UK"),
    "EWJ": ("Xtrackers MSCI Japan UCITS ETF 1C", 0.12, "LU0274209740", "same", "MSCI Japan"),
    "EWC": (
        "iShares MSCI Canada UCITS ETF (Acc)",
        0.48,
        "IE00B52SF786",
        "capped",
        "MSCI Canada",
    ),
    "EWL": (
        "Amundi MSCI Switzerland UCITS ETF CHF",
        0.25,
        "LU1681044993",
        "capped",
        "MSCI Switzerland",
    ),
    "EWA": ("iShares MSCI Australia UCITS ETF", 0.5, "IE00B5377D42", "same", "MSCI Australia"),
    "EEM": (
        "iShares MSCI EM UCITS ETF (Acc)",
        0.18,
        "IE00B4L5YC18",
        "same",
        "MSCI Emerging Markets",
    ),
    "AAXJ": (
        "iShares MSCI EM Asia UCITS ETF (Acc)",
        0.2,
        "IE00B5L8K969",
        "similar",
        "MSCI Emerging Markets Asia",
    ),
    "FXI": ("iShares China Large Cap UCITS ETF", 0.74, "IE00B02KXK85", "same", "FTSE China 50"),
    "EWZ": ("Xtrackers MSCI Brazil UCITS ETF 1C", 0.25, "LU0292109344", "capped", "MSCI Brazil"),
    "EWY": (
        "Xtrackers MSCI Korea UCITS ETF 1C",
        0.45,
        "LU0292100046",
        "capped",
        "MSCI Korea 20/35 Custom",
    ),
    "EWT": (
        "Xtrackers MSCI Taiwan UCITS ETF 1C",
        0.65,
        "LU0292109187",
        "capped",
        "MSCI Taiwan 20/35 Custom",
    ),
    "INDA": (
        "Xtrackers MSCI India Swap UCITS ETF 1C",
        0.19,
        "LU0514695187",
        "same",
        "MSCI India",
    ),
    "SHY": (
        "iShares USD Treasury Bond 1-3yr UCITS ETF (Dist)",
        0.07,
        "IE00B14X4S71",
        "same",
        "ICE US Treasury 1-3 Year",
    ),
    "IEI": (
        "iShares USD Treasury Bond 3-7yr UCITS ETF (Acc)",
        0.07,
        "IE00B3VWN393",
        "same",
        "ICE US Treasury 3-7 Year",
    ),
    "IEF": (
        "iShares USD Treasury Bond 7-10yr UCITS ETF (Acc)",
        0.07,
        "IE00B3VWN518",
        "same",
        "ICE US Treasury 7-10 Year",
    ),
    "TLT": (
        "iShares USD Treasury Bond 20+yr UCITS ETF USD (Dist)",
        0.07,
        "IE00BSKRJZ44",
        "same",
        "ICE US Treasury 20+ Year",
    ),
    "TIP": (
        "iShares USD TIPS UCITS ETF USD (Acc)",
        0.1,
        "IE00B1FZSC47",
        "similar",
        "Bloomberg US Government Inflation-Linked Bond",
    ),
    "AGG": (
        "iShares US Aggregate Bond UCITS ETF (Dist)",
        0.25,
        "IE00B44CGS96",
        "same",
        "Bloomberg US Aggregate Bond",
    ),
    "MBB": (
        "iShares US Mortgage Backed Securities UCITS ETF",
        0.28,
        "IE00BZ6V7883",
        "same",
        "Bloomberg US Mortgage Backed Securities",
    ),
    "VCSH": (
        "State Street SPDR Bloomberg 1-5 Year U.S. Corporate Bond UCITS ETF USD Unhedged (Acc)",
        0.08,
        "IE0002H3JQ66",
        "same",
        "Bloomberg USD Corporate Bonds 1-5 Years",
    ),
    "VCIT": (
        "State Street SPDR Bloomberg 1-10 Year U.S. Corporate Bond UCITS ETF USD Unhedged (Dist)",
        0.12,
        "IE00BYV12Y75",
        "similar",
        "Bloomberg US Intermediate Corporate Bond",
    ),
    "LQD": (
        "iShares USD Corporate Bond UCITS ETF (Dist)",
        0.2,
        "IE0032895942",
        "same",
        "iBoxx USD Liquid Investment Grade",
    ),
    "FLOT": (
        "iShares USD Floating Rate Bond UCITS ETF",
        0.1,
        "IE00BZ048462",
        "same",
        "Bloomberg US Floating Rate Notes 1-5",
    ),
    "HYG": (
        "iShares USD High Yield Corporate Bond UCITS ETF USD (Dist)",
        0.5,
        "IE00B4PY7Y77",
        "capped",
        "iBoxx USD Liquid High Yield Capped",
    ),
    "CWB": (
        "State Street SPDR FTSE Global Convertible Bond UCITS ETF USD Unhedged (Dist)",
        0.5,
        "IE00BNH72088",
        "similar",
        "FTSE Qualified Global Convertible",
    ),
    "EMB": (
        "iShares J.P. Morgan USD Emerging Markets Bond UCITS ETF (Acc)",
        0.45,
        "IE00BYXYYK40",
        "similar",
        "JP Morgan EMBI Global Core",
    ),
    "BWX": (
        "Amundi Global ex-US Government Bond UCITS ETF Acc",
        0.2,
        "LU3254330437",
        "similar",
        "Bloomberg Global Treasury Large Markets DM ex US",
    ),
    "BNDX": (
        "State Street SPDR Bloomberg Global Aggregate Bond UCITS ETF USD Hedged (Acc)",
        0.1,
        "IE00BKC94M46",
        "similar",
        "Bloomberg Global Aggregate Bond (USD Hedged)",
    ),
    "VNQ": (
        "iShares US Property Yield UCITS ETF",
        0.4,
        "IE00B1FZSF77",
        "similar",
        "FTSE EPRA/NAREIT United States Dividend+",
    ),
    "GLD": (
        "Xetra-Gold",
        0,
        "DE000A0S9GB0",
        "same",
        "Gold",
        "an exchange-traded commodity backed by gold, not a UCITS fund",
    ),
    "DBC": (
        "iShares Diversified Commodity Swap UCITS ETF",
        0.19,
        "IE00BDFL4P12",
        "similar",
        "Bloomberg Commodity",
    ),
}
UCITS_TWINS: dict[str, Twin] = {
    ticker: Twin(name, pct / 100, isin, match, index, *note)
    for ticker, (name, pct, isin, match, index, *note) in _TWIN_TABLE.items()
}


def twin_coverage(weights: Mapping[str, float]) -> dict[str, float]:
    """For an allocation of US-listed ETFs: the shares of its invested weight whose ETF has a
    UCITS twin on the same index (capped differently or not), on a similar index, or none,
    and the twins' average expense ratio over the weight they cover."""
    shares = {"same": 0.0, "similar": 0.0, "none": 0.0}
    cost = 0.0
    for ticker, weight in weights.items():
        twin = UCITS_TWINS.get(ticker)
        if twin is None:
            shares["none"] += weight
            continue
        shares["similar" if twin.match == "similar" else "same"] += weight
        cost += weight * twin.expense_ratio
    invested = sum(shares.values())
    covered = shares["same"] + shares["similar"]
    result = {key: value / invested if invested > 0 else 0.0 for key, value in shares.items()}
    result["expense_ratio"] = cost / covered if covered > 0 else float("nan")
    return result


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
