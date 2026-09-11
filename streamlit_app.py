"""FundClone web app. Run with `streamlit run streamlit_app.py`.

Links carry the analysis: ?ticker=AGTHX or ?portfolio=VTI 60, BND 40, plus every setting
that differs from the default, such as &start=2015-01-01&etfs=5.
"""

from __future__ import annotations

import datetime as dt
import math
import os
import re
from pathlib import Path

import pandas as pd
import streamlit as st

from fundclone import charts, etfs
from fundclone.analysis import Analysis, run_analysis
from fundclone.attribution import FACTOR_DESCRIPTIONS, FACTOR_NAMES
from fundclone.data import REGIONS, fetch_info, fetch_prices, load_french_factors
from fundclone.factsheet import parse_factsheet_safely
from fundclone.portfolio import is_ticker, parse_portfolio, whole_shares
from fundclone.replication import ReplicationConfig
from fundclone.report import (
    EQUITY_SHARE_FOR_SCREEN,
    closet_index_check,
    headline,
    interval,
    too_short,
)

st.set_page_config(page_title="FundClone", layout="wide")

AUTOMATIC = "Automatic"
EXAMPLES = ["AGTHX", "DODGX", "FCNTX", "PRWCX", "PTTRX"]
EXAMPLE_PORTFOLIO = "VTI 60, VXUS 30, BND 10"
MAX_ETFS = {AUTOMATIC: None, "3": 3, "5": 5, "8": 8, "12": 12}
REBALANCE = {"Monthly": "M", "Quarterly": "Q"}
FIT_ON = {"Auto": "auto", "Daily": "daily", "Weekly": "weekly"}
FREQUENCIES = ["monthly", "daily"]
BOND_CHOICES = {AUTOMATIC: None, "Include": True, "Exclude": False}
EARLIEST = dt.date(1990, 1, 1)
TODAY = dt.date.today()
WINDOW = (63, 756, 21)  # slider range and step, trading days
ROLLING = (24, 60, 6)  # months
FEE_GROWTH = 0.06  # yearly growth before fees assumed when adding up fees over a horizon
DEFAULTS = {
    "mode": "Fund",
    "target": "AGTHX",
    "start": "2005-01-01",
    "end": TODAY.isoformat(),
    "max_etfs": None,
    "asset_classes": tuple(etfs.ASSET_CLASSES),
    "window": 378,
    "rebalance": "M",
    "fit_on": "auto",
    "cost_bps": 5.0,
    "frequency": "monthly",
    "region": None,
    "bond_factors": None,
    "rolling_window": 36,
}
PLOT_CONFIG = {"displaylogo": False}
DISCLAIMER = (
    "Research and education only: not investment advice or a recommendation to buy or sell "
    "any security. Past performance does not predict future results, and the data may "
    "contain errors. Prices come from Yahoo Finance for personal, non-commercial use. "
    "FundClone is not affiliated with Yahoo, ESMA, Kenneth French or any fund company."
)
ESMA_PAPER = (
    "https://www.esma.europa.eu/sites/default/files/library/esmawp-2020-2_closet_indexing.pdf"
)
_MARKDOWN = re.compile(r"([\\`*_{}\[\]()#+\-.!|<>~$:])")
_AUTOLINK = re.compile(r"(?i)(https?|www)(?=[:.])|(@)")


def plain(text) -> str:
    """Text for Streamlit's markdown that shows as written: links, formatting or LaTeX in
    user input or third-party data are not rendered. Markdown turns bare web and e-mail
    addresses into links whether or not they are escaped, so they get an invisible break."""
    text = _AUTOLINK.sub(lambda m: m.group(0) + "\u200b", str(text))
    return _MARKDOWN.sub(r"\\\1", text)


METHOD = f"""
**The clone.** At the end of every month FundClone looks at the fund's daily returns
over the past 18 months and finds the long-only mix of {len(etfs.ETFS)} liquid US-listed
ETFs (size and style, sectors, industries, factors, regions, bonds, gold, commodities)
that would have followed it most closely. Recent days count more (a 63-day half-life),
weights the data cannot tell apart stay close to last month's, and positions below 2%
are dropped. The mix is bought the next trading day and held, drifting with prices,
until the next month. What is not invested sits in T-bills. Every trade pays a trading
cost, and funds priced outside US trading hours are fitted on weekly returns. The
estimator came out of an out-of-sample comparison of seven approaches on 41 funds, whose
median tracking errors differed by at most 0.15 percentage points; compared with plain
least squares it trades about half as much for about the same tracking error (see the
benchmark in the repository).

**Out of sample, always.** The clone's weights on any day come only from data before
that day. Tracking error, R² and the fund-minus-clone return are measured on these
out-of-sample returns, so they show what someone copying the fund in real time would have
got, not how well a model fits the past. They are computed on weekly returns, because
daily closing prices are noisy: two ETFs that both hold the S&P 500 differ by almost 1% a
year on daily returns and by half that on weekly returns, and some daily mutual fund
prices on Yahoo Finance are stale. Before fitting, a day on which the fund's price did not
change although the market moved enough to move it is merged with the next day. For funds
and ETFs, prices that jump and come back within days on a calm market are left out as
data errors, and unadjusted splits are corrected.

**Fund minus clone.** Both return series are after fees: the fund's prices are net of
its expense ratio, the ETFs' prices net of theirs, and the clone pays trading costs on
top. The gap is the difference in compound annual growth. If its 95% range lies above
zero, the manager added something cheap ETFs could not. A range that straddles zero
means the difference is within the noise.

**Closet index screen.** For equity funds with a year or more of out-of-sample returns,
FundClone applies the three returns-based thresholds of an ESMA working paper on potential
closet index funds ([Danieli, Harris and Pichini, 2020]({ESMA_PAPER})): tracking error
below 3%, R² above 95% and beta between 0.95 and 1.05. The paper states its authors'
views, not an official ESMA test. It measured the thresholds against each fund's own
benchmark; FundClone uses the ETF, out of its {len(etfs.ETFS)}, that tracked the fund most
closely. Where one of them follows the fund's benchmark, that makes the thresholds easier
to meet. Where none does, as for total international or all-world indices, it can make
them harder, so failing the screen does not clear a fund. An active fund that meets all
three is a candidate for a closer look, not proof of anything; for an index fund it is
expected.

**Factor exposures.** A second, academic view regresses the fund's monthly excess returns
on the Fama-French five factors and momentum, with term and credit factors for funds
that hold bonds, and splits the average return into factor contributions and alpha.

**Data.** Prices and fund expense ratios from Yahoo Finance; factors and the T-bill rate
from the Kenneth French data library, which lags by one to two months. ETF expense
ratios as of {etfs.EXPENSE_RATIOS_AS_OF}. Yahoo Finance data is for personal,
non-commercial use; this app is a free, non-commercial demo.

**Privacy.** Uploaded factsheets are read in memory to find identifiers and are not
stored. The app runs on Streamlit Community Cloud.

{DISCLAIMER}
"""

# An optional local price snapshot for self-hosted deployments (see CONTRIBUTING.md). The
# repository ships none, because Yahoo Finance data may not be redistributed.
SNAPSHOT = Path(
    os.environ.get("FUNDCLONE_SNAPSHOT", Path(__file__).with_name("data") / "prices.parquet")
)

live_prices = st.cache_data(ttl=dt.timedelta(hours=6), max_entries=64, show_spinner=False)(
    fetch_prices
)


@st.cache_resource(show_spinner=False)
def snapshot() -> pd.DataFrame:
    """The local price snapshot, if there is one, for when Yahoo Finance does not answer."""
    return pd.read_parquet(SNAPSHOT).astype(float) if SNAPSHOT.exists() else pd.DataFrame()


def prices_cached(tickers: list[str], start: str, end: str) -> pd.DataFrame:
    """Prices from Yahoo Finance, cached; tickers Yahoo does not answer for come from the
    snapshot, with a note for the analysis to show."""
    tickers = list(dict.fromkeys(tickers))  # run_analysis may ask for a ticker twice
    live = live_prices(tickers, start, end)
    stored = snapshot()
    fill = [ticker for ticker in tickers if ticker not in live and ticker in stored]
    if not fill:
        return live
    period = (stored.index >= pd.Timestamp(start)) & (stored.index < pd.Timestamp(end))
    prices = pd.concat([live, stored.loc[period, fill]], axis=1).sort_index()
    prices.attrs["notes"] = [
        f"Yahoo Finance did not answer for {', '.join(fill)}, so their prices come from the "
        f"local price snapshot of {stored.index[-1]:%Y-%m-%d}."
    ]
    return prices


DAY = dt.timedelta(days=1)
factors_cached = st.cache_data(ttl=DAY, max_entries=16, show_spinner=False)(load_french_factors)
info_cached = st.cache_data(ttl=DAY, max_entries=256, show_spinner=False)(fetch_info)


@st.cache_data(show_spinner=False, max_entries=32)
def analyse(
    mode,
    target,
    start,
    end,
    max_etfs,
    asset_classes,
    window,
    rebalance,
    fit_on,
    cost_bps,
    frequency,
    region,
    bond_factors,
    rolling_window,
) -> Analysis:
    config = ReplicationConfig(
        window=window,
        rebalance=rebalance,
        frequency=fit_on,
        cost_bps=cost_bps,
        max_etfs=max_etfs,
    )
    return run_analysis(
        parse_portfolio(target) if mode == "Portfolio" else target,
        start,
        end,
        replication=config,
        asset_classes=list(asset_classes),
        frequency=frequency,
        region=region,
        use_bond_factors=bond_factors,
        rolling_window=rolling_window,
        price_loader=prices_cached,
        factor_loader=factors_cached,
        info_loader=info_cached,
    )


def show_table(df: pd.DataFrame, formats: dict[str, str], hide_index: bool = False) -> None:
    """Show a table with fixed number formats, independent of the browser's locale.

    Numbers are rendered to right-aligned text, so a missing value reads as a dash
    rather than Streamlit's "None".
    """
    shown = df.copy()
    if isinstance(shown.index, pd.DatetimeIndex):
        shown.index = shown.index.strftime("%Y-%m-%d")
    for column, fmt in formats.items():
        shown[column] = shown[column].map(lambda v, fmt=fmt: "–" if pd.isna(v) else fmt.format(v))
    config = {column: st.column_config.TextColumn(alignment="right") for column in formats}
    st.dataframe(shown, hide_index=hide_index, column_config=config)


def _date(text: str) -> str:
    value = dt.date.fromisoformat(text)
    if not EARLIEST <= value <= TODAY:
        raise ValueError(text)
    return value.isoformat()


def _choice(*choices):
    def parse(text: str):
        if text not in choices:
            raise ValueError(text)
        return text

    return parse


def _on_grid(low: int, high: int, step: int):
    def parse(text: str) -> int:
        value = int(text)
        if not low <= value <= high or (value - low) % step:
            raise ValueError(text)
        return value

    return parse


def _cap(text: str) -> int:
    value = int(text)
    if value not in MAX_ETFS.values():
        raise ValueError(text)
    return value


def _blocks(text: str) -> tuple[str, ...]:
    names = text.split(",")
    if not names or any(name not in etfs.ASSET_CLASSES for name in names):
        raise ValueError(text)
    return tuple(name for name in etfs.ASSET_CLASSES if name in names)


def _cost(text: str) -> float:
    value = float(text)
    if not 0 <= value <= 50:
        raise ValueError(text)
    return value


def _yes_no(text: str) -> bool:
    if text not in ("yes", "no"):
        raise ValueError(text)
    return text == "yes"


# URL parameter -> (setting, parser); parsers raise ValueError for values the form cannot show
LINK = {
    "start": ("start", _date),
    "end": ("end", _date),
    "etfs": ("max_etfs", _cap),
    "blocks": ("asset_classes", _blocks),
    "window": ("window", _on_grid(*WINDOW)),
    "rebalance": ("rebalance", _choice(*REBALANCE.values())),
    "fit": ("fit_on", _choice(*FIT_ON.values())),
    "cost": ("cost_bps", _cost),
    "factors": ("frequency", _choice(*FREQUENCIES)),
    "region": ("region", _choice(*REGIONS)),
    "bonds": ("bond_factors", _yes_no),
    "rolling": ("rolling_window", _on_grid(*ROLLING)),
}


def _link_text(value) -> str:
    if isinstance(value, tuple):
        return ",".join(value)
    if isinstance(value, bool):
        return "yes" if value else "no"
    if isinstance(value, float):
        return f"{value:g}"
    return str(value)


def params_from_link() -> dict:
    """The defaults, overridden by what the URL carries; values that do not fit are ignored."""
    query = st.query_params
    params = dict(DEFAULTS)
    if query.get("ticker") and is_ticker(query["ticker"].strip()):
        params.update(mode="Fund", target=query["ticker"].strip().upper())
    elif query.get("portfolio"):
        params.update(mode="Portfolio", target=query["portfolio"])
    for key, (setting, parse) in LINK.items():
        if key in query:
            try:
                params[setting] = parse(query[key])
            except ValueError:
                pass
    return params


def update_link(params: dict) -> None:
    """Put the analysis in the URL: the target and every setting that differs from the default."""
    st.query_params.clear()
    st.query_params["ticker" if params["mode"] == "Fund" else "portfolio"] = params["target"]
    for key, (setting, _) in LINK.items():
        if params[setting] != DEFAULTS[setting]:
            st.query_params[key] = _link_text(params[setting])


def settings_form(initial: dict) -> dict | None:
    mode = st.radio(
        "What to clone",
        ["Fund", "Portfolio"],
        index=0 if initial["mode"] == "Fund" else 1,
        horizontal=True,
    )
    with st.form("settings", border=False):
        if mode == "Fund":
            target = st.text_input(
                "Ticker",
                initial["target"] if initial["mode"] == "Fund" else DEFAULTS["target"],
                help="Yahoo Finance symbol of a mutual fund, ETF or stock, e.g. AGTHX or EXS1.DE.",
            )
            st.caption("Try " + ", ".join(EXAMPLES))
        else:
            target = st.text_area(
                "Holdings",
                initial["target"] if initial["mode"] == "Portfolio" else EXAMPLE_PORTFOLIO,
                help="Ticker and weight per entry, separated by commas or new lines.",
            )
        left, right = st.columns(2)
        start = left.date_input(
            "Start",
            dt.date.fromisoformat(initial["start"]),
            min_value=EARLIEST,
            max_value=TODAY,
        )
        end = right.date_input(
            "End", dt.date.fromisoformat(initial["end"]), min_value=EARLIEST, max_value=TODAY
        )
        choices = list(MAX_ETFS)
        current = next((k for k, v in MAX_ETFS.items() if v == initial["max_etfs"]), AUTOMATIC)
        max_etfs = st.selectbox(
            "ETFs in the clone",
            choices,
            index=choices.index(current),
            help="Automatic uses as many ETFs as help; a cap gives a simpler clone to hold.",
        )
        classes = st.multiselect(
            "Building blocks",
            etfs.ASSET_CLASSES,
            default=list(initial["asset_classes"]),
            help=f"{len(etfs.ETFS)} liquid US-listed ETFs in {len(etfs.ASSET_CLASSES)} groups.",
        )
        with st.expander("Advanced"):
            low, high, step = WINDOW
            window = st.slider(
                "Estimation window, trading days", low, high, initial["window"], step=step
            )
            rebalance = st.radio(
                "Rebalancing",
                list(REBALANCE),
                index=list(REBALANCE.values()).index(initial["rebalance"]),
                horizontal=True,
            )
            fit_on = st.radio(
                "Fit on",
                list(FIT_ON),
                index=list(FIT_ON.values()).index(initial["fit_on"]),
                horizontal=True,
                help="Auto uses weekly returns when anything is priced outside US trading hours.",
            )
            cost_bps = st.number_input(
                "Trading cost, bp of traded value", 0.0, 50.0, initial["cost_bps"], step=0.5
            )
            st.markdown("**Factor exposures**")
            frequency = st.radio(
                "Return frequency",
                FREQUENCIES,
                index=FREQUENCIES.index(initial["frequency"]),
                horizontal=True,
                format_func=str.capitalize,
            )
            regions = [AUTOMATIC, *REGIONS]
            region = st.selectbox(
                "Factor region", regions, index=regions.index(initial["region"] or AUTOMATIC)
            )
            bond = st.selectbox(
                "Term and credit factors",
                list(BOND_CHOICES),
                index=list(BOND_CHOICES.values()).index(initial["bond_factors"]),
            )
            low, high, step = ROLLING
            rolling_window = st.slider(
                "Rolling window, months", low, high, initial["rolling_window"], step=step
            )
        if not st.form_submit_button("Build the clone", type="primary", width="stretch"):
            return None
    return {
        "mode": mode,
        "target": target.strip(),
        "start": start.isoformat(),
        "end": end.isoformat(),
        "max_etfs": MAX_ETFS[max_etfs],
        "asset_classes": tuple(classes),
        "window": window,
        "rebalance": REBALANCE[rebalance],
        "fit_on": FIT_ON[fit_on],
        "cost_bps": cost_bps,
        "frequency": frequency,
        "region": None if region == AUTOMATIC else region,
        "bond_factors": BOND_CHOICES[bond],
        "rolling_window": rolling_window,
    }


def factsheet_lookup() -> None:
    with st.expander("Find a ticker from a factsheet"):
        upload = st.file_uploader("Factsheet PDF", type="pdf")
        st.caption(
            "Pulls the fund name, ISINs and ticker candidates out of the first pages of a PDF. "
            "Uploads are read in memory and not stored; the app runs on Streamlit Community "
            "Cloud ([privacy policy](https://streamlit.io/privacy-policy))."
        )
        if upload is None:
            return
        try:
            info = parse_factsheet_safely(upload.getvalue())
        except Exception:  # malformed, encrypted or oversized PDFs fail in the child process
            st.warning("Could not read the PDF.")
            return
        candidates = ", ".join(info["ticker_candidates"]) or "none found"
        st.markdown(f"**{plain(info['fund_name'] or 'Unknown fund')}**")
        st.markdown(f"Ticker candidates: {plain(candidates)}")
        st.markdown(f"ISINs: {plain(', '.join(info['isins']) or 'none found')}")


def orders(allocation: pd.DataFrame, prices: pd.Series, amount: float) -> pd.DataFrame:
    """Whole shares for `amount`, as close to the clone's weights as it allows (see
    portfolio.whole_shares), with the weights they give; the rest stays in cash."""
    held = allocation[allocation["ETF"] != "Cash"]
    targets = dict(zip(held["ETF"], held["Weight"], strict=True))
    shares = whole_shares(targets, prices, amount)
    rows = []
    for ticker, target in targets.items():
        price = float(prices.get(ticker, float("nan")))
        value = shares[ticker] * price
        rows.append(
            {
                "ETF": ticker,
                "Price": price,
                "Shares": shares[ticker],
                "Value": value,
                "Target": target,
            }
        )
    invested = sum(row["Value"] for row in rows if not math.isnan(row["Value"]))
    cash_target = 1 - sum(targets.values())
    rows.append(
        {
            "ETF": "Cash",
            "Price": None,
            "Shares": None,
            "Value": amount - invested,
            "Target": cash_target,
        }
    )
    table = pd.DataFrame(rows)
    table.insert(4, "Weight", table["Value"] / amount)
    return table


def fee_cost(amount: float, expense_ratio: float, years: int) -> float:
    """End wealth lost to fees over `years` on money growing FEE_GROWTH a year before fees."""
    return amount * (1 + FEE_GROWTH) ** years * (1 - (1 - expense_ratio) ** years)


def render_verdict(a: Analysis) -> None:
    t = a.tracking
    with st.container(border=True):
        st.markdown(plain(" ".join(headline(a))))

    short = too_short(a)
    caveat = (
        f" From only {t['observations']} weeks of out-of-sample returns, too few to rely on."
        if short
        else ""
    )
    cols = st.columns(4)
    cols[0].metric(
        "Tracking error p.a.",
        f"{t['tracking_error']:.2%}",
        help="Annualised volatility of the weekly return gap between fund and clone. Weekly "
        "returns keep day-to-day pricing noise of mutual funds out of the figure." + caveat,
    )
    cols[1].metric(
        "Explained by the clone",
        f"{t['r_squared']:.0%}",
        help="Out-of-sample R² on weekly returns: 1 − var(fund − clone) / var(fund)." + caveat,
    )
    if short:
        years = t["observations"] / t["periods_per_year"]
        gap = (1 + t["fund_return"]) ** years - (1 + t["clone_return"]) ** years
        cols[2].metric(
            "Fund minus clone",
            f"{gap:+.2%}",
            help=f"Return difference over only {t['observations']} weeks, too few to annualise.",
        )
    else:
        low, high = interval(t)
        cols[2].metric(
            "Fund minus clone p.a.",
            f"{t['active_return']:+.2%}",
            help="Difference in compound annual return after all fees; "
            f"95% range {low:+.2%} to {high:+.2%}.",
        )
    if a.expense_ratio is not None:
        cols[3].metric(
            "Clone fees p.a.",
            f"{a.clone_expense_ratio:.2%}",
            delta=f"{a.clone_expense_ratio - a.expense_ratio:+.2%} vs the fund",
            delta_color="inverse",
            help=f"Weighted ETF expense ratio. The fund charges {a.expense_ratio:.2%}.",
        )
    else:
        cols[3].metric(
            "Clone fees p.a.", f"{a.clone_expense_ratio:.2%}", help="Weighted ETF expense ratio."
        )

    check = closet_index_check(a)
    if check:
        measured = (
            f"tracking error {check['tracking_error']:.1%}, R² {check['r_squared']:.0%}, "
            f"beta {check['beta']:.2f} against {a.closest_etf}"
        )
        if check["flagged"] and check["passive"]:
            st.caption(
                f"Closet-index screen: {measured}. All three thresholds are met, as expected "
                "for an index fund; an actively managed fund that meets them stays very close "
                "to its benchmark."
            )
        elif check["flagged"]:
            st.warning(
                f"Meets all three closet-indexing thresholds of an ESMA working paper "
                f"({measured}). If {a.label} is actively managed, that is worth a closer look "
                "before paying active fees; for an index fund it is expected. The Method tab "
                "explains the screen and its limits."
            )
        else:
            failed = [label for label, ok in check["checks"].items() if not ok]
            st.caption(
                f"Closet-index screen: {measured}. Not met: {', '.join(failed)}. Against the "
                "fund's own benchmark the result could differ; the Method tab explains the "
                "screen and its limits."
            )
    elif not a.holdings and a.equity_share >= EQUITY_SHARE_FOR_SCREEN:
        st.caption("The closet-index screen needs a year or more of out-of-sample returns.")
    for note in a.notes:
        st.caption(plain(note))


def render_clone(a: Analysis, params: dict, mode: str) -> None:
    rep = a.replication
    cfg = rep.config
    allocation = a.allocation()
    left, right = st.columns([3, 2], gap="large")
    with left:
        st.markdown(f"**The clone today**, traded {rep.weights.index[-1]:%d %b %Y}")
        show_table(allocation, {"Weight": "{:.1%}", "Expense ratio": "{:.2%}"}, hide_index=True)
        st.caption(
            f"Rebalanced {'monthly' if cfg.rebalance == 'M' else 'quarterly'} on "
            f"{cfg.frequency} returns of the past {cfg.window} trading days. "
            f"Turnover {rep.annual_turnover:.1f}× a year at {cfg.cost_bps:g} bp per trade."
        )
    with right:
        st.markdown("**Build it**")
        st.caption("An illustration at the latest prices, not a recommendation to trade.")
        amount_col, years_col = st.columns([3, 2])
        amount = amount_col.number_input("Amount, USD", 1_000, 10_000_000, 10_000, step=1_000)
        years = years_col.number_input("Years", 1, 40, 10)
        export = allocation
        if a.current_weights.empty:
            st.caption("The clone holds only T-bills at the moment, so there is nothing to buy.")
        else:
            end = (pd.Timestamp(params["end"]) + pd.Timedelta(days=1)).strftime("%Y-%m-%d")
            recent = prices_cached(list(a.current_weights.index), params["start"], end)
            if recent.empty:
                st.caption("Latest prices are not available, so no orders are shown.")
            else:
                buy = orders(allocation, recent.ffill().iloc[-1], amount)
                formats = {"Price": "{:,.2f}", "Shares": "{:,.0f}", "Value": "{:,.0f}"}
                show_table(buy, {**formats, "Weight": "{:.1%}", "Target": "{:.1%}"}, True)
                etf_rows = buy[buy["ETF"] != "Cash"]
                gap = (etf_rows["Weight"] - etf_rows["Target"]).abs().max()
                st.caption(
                    f"Whole shares at the latest close, as close to the clone's weights as "
                    f"{amount:,.0f} USD allows; the rest stays in cash. The largest gap to a "
                    f"target weight is {gap:.1%}."
                )
                export = allocation.merge(buy[["ETF", "Shares"]], on="ETF", how="left")
        if a.expense_ratio is not None:
            st.caption(
                f"Over {years} years, if the money grew {FEE_GROWTH:.0%} a year before fees, "
                f"fees would take about {fee_cost(amount, a.expense_ratio, years):,.0f} USD in "
                f"the fund and {fee_cost(amount, a.clone_expense_ratio, years):,.0f} in the clone."
            )
        st.download_button(
            "Download the clone as CSV",
            export.to_csv(index=False).encode(),
            file_name=f"fundclone-{a.label.lower()}.csv",
            mime="text/csv",
        )

    st.markdown("**How the clone changed over time**")
    st.plotly_chart(charts.weights(rep.weights, mode), theme=None, config=PLOT_CONFIG)
    with st.expander("All weights as a table"):
        history = rep.weights.loc[:, rep.weights.abs().max() > 1e-4]
        history = history.assign(Cash=rep.cash).iloc[::-1]
        show_table(history, dict.fromkeys(history.columns, "{:.1%}"))


def render_performance(a: Analysis, mode: str) -> None:
    r = a.returns
    st.markdown("**Growth of 100**")
    st.plotly_chart(
        charts.growth(r, a.labels, a.replication.weights.index[0], mode),
        theme=None,
        config=PLOT_CONFIG,
    )
    performance = a.performance.rename(
        columns={
            "annual_return": "Annual return",
            "volatility": "Volatility",
            "sharpe": "Sharpe ratio",
            "max_drawdown": "Max drawdown",
            "total_return": "Total return",
        }
    )
    show_table(
        performance,
        {
            "Annual return": "{:.2%}",
            "Volatility": "{:.2%}",
            "Sharpe ratio": "{:.2f}",
            "Max drawdown": "{:.1%}",
            "Total return": "{:.0%}",
        },
    )
    if too_short(a):
        st.caption(
            f"{a.closest_etf} is shown for comparison only: {a.tracking['observations']} weeks "
            "of out-of-sample returns are too few to call any single ETF the closest."
        )
    else:
        st.caption(
            f"{a.closest_etf} is the single ETF that tracked {a.label} most closely over the "
            f"same weeks, chosen with hindsight: tracking error "
            f"{a.closest_tracking['tracking_error']:.1%} against "
            f"{a.tracking['tracking_error']:.1%} for the clone."
        )
    left, right = st.columns(2, gap="large")
    with left:
        st.markdown("**Drawdown**")
        st.plotly_chart(charts.drawdowns(r, a.labels, mode), theme=None, config=PLOT_CONFIG)
    with right:
        st.markdown("**Tracking error**, trailing year of weekly returns")
        if len(a.tracking_returns) <= a.tracking_periods_per_year:
            st.caption("Needs more than a year of out-of-sample returns.")
        else:
            st.plotly_chart(
                charts.rolling_tracking_error(
                    a.tracking_returns, a.tracking_periods_per_year, mode
                ),
                theme=None,
                config=PLOT_CONFIG,
            )


def render_attribution(a: Analysis, mode: str) -> None:
    att = a.attribution
    if att is None:
        st.caption("The history is too short for a factor regression.")
        return
    unit = "months" if a.frequency == "monthly" else "trading days"
    model = "Fama-French five factors and momentum"
    if a.bond_factors:
        model += ", plus term and credit"
    st.caption(
        f"{a.frequency.capitalize()} excess returns over the T-bill, {att.start:%b %Y} to "
        f"{att.end:%b %Y} ({att.n_obs} {unit}); {model}, {a.region} version. "
        f"Newey-West standard errors with {att.hac_lags} lags."
    )
    cols = st.columns(4)
    cols[0].metric(
        "Alpha p.a.",
        f"{att.alpha:.2%}",
        help="Regression intercept, annualised: average excess return the factors do not explain.",
    )
    cols[1].metric(
        "Alpha t-stat",
        f"{att.alpha_tstat:.2f}",
        help="Values beyond ±2 are roughly significant at the 5% level.",
    )
    cols[2].metric(
        "R²",
        f"{att.r_squared:.2f}",
        help="Share of the variance of excess returns explained by the factors.",
    )
    cols[3].metric(
        "Residual volatility p.a.",
        f"{att.residual_vol:.2%}",
        help="Annualised volatility of the part of returns the factors do not explain.",
    )

    left, right = st.columns(2, gap="large")
    with left:
        st.markdown("**Factor loadings** with 95% confidence intervals")
        st.plotly_chart(charts.loadings(att, mode), theme=None, config=PLOT_CONFIG)
    with right:
        st.markdown(
            f"**Sources of the average excess return** of {att.mean_excess_return:.2%} p.a."
        )
        st.plotly_chart(charts.contributions(att, mode), theme=None, config=PLOT_CONFIG)

    table = att.table()
    table.insert(
        1,
        "Definition",
        [FACTOR_DESCRIPTIONS.get(key, "Return the factors do not explain") for key in table.index],
    )
    show_table(
        table,
        {
            "Loading": "{:.2f}",
            "t-stat": "{:.2f}",
            "p-value": "{:.3f}",
            "Contribution p.a.": "{:.2%}",
        },
        hide_index=True,
    )

    st.markdown(f"**Rolling loadings**, trailing {a.rolling_window} months")
    if a.rolling_betas.empty:
        st.caption("The sample is shorter than the rolling window.")
        return
    st.plotly_chart(charts.rolling_loadings(a.rolling_betas, mode), theme=None, config=PLOT_CONFIG)
    with st.expander("Rolling loadings as a table"):
        rolling = a.rolling_betas.rename(columns=FACTOR_NAMES).iloc[::-1]
        show_table(rolling, dict.fromkeys(rolling.columns, "{:.2f}"))


def render(a: Analysis, params: dict, mode: str) -> None:
    r = a.returns
    title = a.name if a.holdings else f"{a.name} ({a.label})"
    st.subheader(plain(title))
    st.caption(f"Out of sample {r.index[0]:%b %Y} to {r.index[-1]:%b %Y} · returns in USD")
    render_verdict(a)
    clone_tab, performance_tab, factor_tab, method_tab = st.tabs(
        ["Clone", "Performance", "Factor exposures", "Method"]
    )
    with clone_tab:
        render_clone(a, params, mode)
    with performance_tab:
        render_performance(a, mode)
    with factor_tab:
        render_attribution(a, mode)
    with method_tab:
        st.markdown(METHOD)


def main() -> None:
    initial = params_from_link()
    with st.sidebar:
        submitted = settings_form(initial)
        factsheet_lookup()
    if submitted:
        st.session_state["params"] = submitted
        update_link(submitted)
    params = st.session_state.get("params", initial)

    st.title("FundClone")
    st.caption(
        "Clone any fund or portfolio with a handful of low-cost ETFs, "
        "and see what the manager adds after fees."
    )
    st.caption(DISCLAIMER)
    if not params["target"]:
        st.error("Enter a ticker or a portfolio.")
        return
    if params["mode"] == "Fund" and not is_ticker(params["target"]):
        st.error("That does not look like a Yahoo Finance ticker, such as AGTHX or EXS1.DE.")
        return
    if params["start"] >= params["end"]:
        st.error("The start date must come before the end date.")
        return
    if not params["asset_classes"]:
        st.error("Choose at least one group of building blocks.")
        return
    try:
        with st.spinner("Loading prices and building the clone"):
            analysis = analyse(**params)
    except Exception as exc:  # data gaps, bad tickers and bad portfolios surface as messages
        st.error(f"Could not build the clone: {plain(exc)}")
        return
    render(analysis, params, "dark" if st.context.theme.type == "dark" else "light")


main()
