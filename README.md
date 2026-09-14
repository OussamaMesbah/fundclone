# FundClone

**Is your active fund worth its fee?** FundClone clones any mutual fund, ETF or
portfolio with a handful of low-cost ETFs, and measures, strictly out of sample, how
much of the fund you get from the clone and what the manager adds on top after fees.

[![tests](https://github.com/OussamaMesbah/fundclone/actions/workflows/tests.yml/badge.svg?branch=master)](https://github.com/OussamaMesbah/fundclone/actions/workflows/tests.yml)
[![release](https://img.shields.io/github/v/release/OussamaMesbah/fundclone)](https://github.com/OussamaMesbah/fundclone/releases)
![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue)
[![License: MIT](https://img.shields.io/badge/license-MIT-green)](https://github.com/OussamaMesbah/fundclone/blob/master/LICENSE)
[![Open the app](https://static.streamlit.io/badges/streamlit_badge_black_white.svg)](https://fundclone.streamlit.app)

![The FundClone app cloning the American Funds Growth Fund of America](https://raw.githubusercontent.com/OussamaMesbah/fundclone/master/docs/screenshot.png)

## What you get

- **A verdict.** How much of the fund's week-to-week behaviour a cheap ETF clone
  reproduces, how much faster or slower the fund grew than its clone after all fees
  (with a 95% range), and whether it meets the closet-indexing thresholds of an ESMA
  working paper.
- **A clone you can buy.** Typically seven to ten liquid ETFs, their weights, whole-share
  orders for any amount, what the fees add up to and a CSV to take to your broker. Cap
  it at three or five ETFs if you prefer something simpler.
- **An X-ray.** Fama-French factor exposures with Newey-West errors, how they drifted
  over time, and the single ETF that comes closest to the fund.

It works for funds, ETFs and stocks with about 19 months of price history or more on
Yahoo Finance, and for your own portfolio typed as `VTI 60, VXUS 30, BND 10`.

> **Disclaimer.** FundClone is for research and education. It is not investment advice or
> a recommendation to buy or sell any security, past performance does not predict future
> results, and the data may contain errors. FundClone is not affiliated with Yahoo, ESMA,
> Kenneth French or any fund company.

## Quickstart

```bash
git clone https://github.com/OussamaMesbah/fundclone.git && cd fundclone
python3 -m venv .venv && source .venv/bin/activate    # Python 3.10 or newer
pip install -e ".[app]"
fundclone AGTHX
```

```text
American Funds Growth Fd of Amer A (AGTHX), out of sample 2006-08-02 to 2026-09-10

A clone of 10 ETFs explains 98% of the variation in AGTHX's weekly returns out of sample, with a tracking error of 2.3% a year.
The clone costs 0.27% a year in ETF fees; the fund charges 0.59%.
AGTHX returned 0.2% a year more than its clone after all fees; the 95% range is -0.9% to +1.3%, so the gap is within the noise.
The closest single ETF, IWF, tracks with 4.2% tracking error.

Clone as of 2026-09-01:
  IWF    Russell 1000 Growth                  32.0%
  FDN    Internet                             14.8%
  XLY    Consumer Discretionary               10.4%
  AAXJ   MSCI All Country Asia ex Japan        8.8%
  ...
```

The web app at [fundclone.streamlit.app](https://fundclone.streamlit.app) shows the same
analysis with charts, a shopping list and links that carry every setting, such as
[`?ticker=AGTHX&etfs=5`](https://fundclone.streamlit.app/?ticker=AGTHX&etfs=5). To run it
locally:

```bash
streamlit run streamlit_app.py
```

The hosted app is a free, non-commercial demo. Factsheets uploaded there are read in memory
and not stored.

## How accurate is it?

Tracking error measures how far the fund and its clone drift apart each year. Every
clone return below comes after the data used to choose the weights that earned it, and
after trading costs. FundClone was developed on 41 funds. The table shows 23 other US
mutual funds across the same categories, picked once development was finished and run
once with the final code:

| 23 fresh funds, 2010 to 2026 | Median tracking error | Mean tracking error | Median R² | ETFs held |
|---|---|---|---|---|
| Before 0.3: 4-7 hand-picked ETFs | 3.78% | 4.44% | 0.930 | 2.9 |
| **FundClone 0.3** | **2.89%** | **2.92%** | **0.966** | **7.8** |
| FundClone 0.3, at most 5 ETFs | 3.00% | 3.02% | 0.963 | 4.6 |

With 23 funds the median itself is uncertain: drawing the funds again and again with
replacement (a bootstrap) puts it between 2.3% and 3.2% with 95% confidence. Compared fund
by fund, the clone tracks 0.54 percentage points more closely in the median, with a 95%
range of 0.25 to 1.31 points. The 81 ETFs were picked in 2026, with hindsight; limited to
the 68 that were already trading in January 2009, a year before scoring starts, the median
over all 64 funds stays at 2.91%.

The clone tracks more closely than before on 22 of the 23 funds; the exception is an S&P
500 index fund (0.60% before, 0.63% now). Plain least squares on the same 81 ETFs tracks
about as closely (2.84%) but trades twice as much and holds 13 ETFs. On the 41
development funds the picture is the same: a median of 3.66% before and 2.93% now. By
category, over the whole benchmark:

| Category | Funds | Before | 0.3 | Example |
|---|---|---|---|---|
| Index funds | 4 | 0.6% | 0.6% | VFIAX 0.6% |
| US large-cap | 15 | 3.9% | 3.1% | AGTHX 2.2% |
| US small/mid-cap | 7 | 4.2% | 3.2% | VEXPX 2.1% |
| International | 10 | 4.5% | 3.7% | HAINX 3.0% |
| Global | 2 | 3.1% | 2.3% | ANWPX 2.3% |
| Balanced | 9 | 2.4% | 1.8% | FBALX 1.3% |
| Bond | 9 | 1.9% | 1.8% | VBTLX 1.2% |
| Sector | 7 | 13.3% | 4.6% | VGHCX 3.7% |
| Single stock | 1 | 11.8% | 10.7% | BRK-B |

What remains is mostly what the manager does that no ETF combination can: picking
individual stocks. For a fund with 2% tracking error that is a small bet; for ARKK (21%)
or Berkshire Hathaway (11%) it is a large part of the story. The protocol, the results for every
fund, a comparison of seven estimation methods and the commands to reproduce every
number are in [benchmarks/](https://github.com/OussamaMesbah/fundclone/blob/master/benchmarks/README.md).

## How it works

FundClone builds on returns-based style analysis
([Sharpe, 1992](https://web.stanford.edu/~wfsharpe/art/sa/sa.htm)): a fund's returns are
explained by a long-only mix of asset-class returns. Sharpe fitted that mix once, over the
whole history, to describe a fund's style. FundClone refits it every month from past data
only, on ETFs you can buy, and measures out of sample, after trading costs, how closely the
clone follows the fund and what the fund returns beyond it.

1. **Building blocks.** 81 liquid US-listed ETFs: size and style, the eleven sectors, 16
   industries, factor ETFs, developed and emerging regions, 18 bond ETFs, REITs, gold and
   commodities. ETFs join once they have enough history.
2. **Monthly re-estimation.** At each month-end the long-only ETF mix that best follows
   the fund's daily excess returns over the past 18 months is found by constrained least
   squares. Recent days count more (63-day half-life), weights the data cannot tell apart
   stay close to last month's, and positions below 2% are dropped.
3. **Realistic trading.** The new weights are traded at the next day's close and drift
   with prices until the following month. Every trade pays 5 bp; anything not invested
   sits in T-bills.
4. **Honest measurement.** Tracking error, R² and the fund-minus-clone return are
   computed on weekly out-of-sample returns, and the return gap is the difference in
   compound growth. Its 95% range uses a Newey-West standard error, which widens it when
   a gap tends to carry over from one week to the next. The verdict also sets the fund
   against the closest single ETF, the simplest alternative to it. Yahoo Finance sometimes repeats a mutual fund's previous price and
   catches up a day later, so a day on which the price did not change although the
   market moved enough to move it is merged with the next. For funds and ETFs, prices
   that jump and come back within days on a calm market are dropped as data errors, and
   unadjusted splits are corrected.
5. **Factor view.** Monthly excess returns are regressed on the Fama-French five factors
   and momentum, with term and credit factors when the clone holds bonds, and the average
   return is split into factor contributions and alpha.

Funds priced outside US trading hours are converted to USD where needed and fitted on
weekly returns.

## Python

```python
from fundclone import ReplicationConfig, run_analysis

fund = run_analysis("DODGX", start="2005-01-01", end="2026-09-01")
fund.tracking["tracking_error"], fund.tracking["r_squared"]
fund.allocation()  # the clone today, with expense ratios
fund.attribution.table()  # factor loadings, t-stats, contributions

mix = {"VTI": 60, "VXUS": 30, "BND": 10}
three = ReplicationConfig(max_etfs=3)
portfolio = run_analysis(mix, "2012-01-01", "2026-09-01", replication=three)
```

## Related tools

Returns-based style analysis is a standard tool. Portfolio Visualizer offers it together
with factor regressions and manager performance analysis, and Interactive Brokers gives
its clients a Mutual Fund Replicator that suggests ETFs in place of a mutual fund.
FundClone differs in that every clone is tested out of sample with trading costs, and it
is open source under the MIT license, benchmark included.

## Limitations

- Stock selection cannot be cloned from returns. For concentrated funds the tracking
  error stays high; that is the size of the active bet you pay for.
- The ETFs are US-listed. Investors in the EU generally cannot buy them and need UCITS
  equivalents, which FundClone does not cover yet.
- The first clone needs about 19 months of prices (18 to fit it), and figures from less
  than a year of out-of-sample returns mean little: the verdict says so and leaves out
  the ESMA screen.
- Prices come from Yahoo Finance through yfinance. They have gaps and errors, and Yahoo's
  terms allow personal, non-commercial use only, so the repository ships no Yahoo data.
- The Kenneth French factors lag by one to two months, and they are long/short paper
  portfolios: alpha against them is not a return you could have earned.
- The closet-index screen applies thresholds from an [ESMA working paper](https://www.esma.europa.eu/sites/default/files/library/esmawp-2020-2_closet_indexing.pdf)
  (Danieli, Harris and Pichini, 2020), which states its authors' views, not an official
  ESMA test. It uses the closest of the 81 ETFs instead of the fund's official
  benchmark. Where one of them follows that benchmark, the thresholds are easier to
  meet; where none does, as for total international or all-world indices, they can be
  harder, so failing the screen does not clear a fund.
- Only funds that still exist can be analysed, so any comparison across funds favours
  the survivors.
- The 81 ETFs were picked in 2026, and ETFs that have closed since are missing from it.
  Limited to the 68 that already traded in January 2009, the benchmark's median tracking
  error does not change, but closed ETFs cannot be tested.

## Roadmap

- UCITS building blocks for European investors, with a curated list of Xetra ETFs.
- Look-through of US fund holdings from SEC N-PORT filings.
- Screening many funds at once.

## Contributing

Contributions are welcome.
[CONTRIBUTING.md](https://github.com/OussamaMesbah/fundclone/blob/master/CONTRIBUTING.md)
explains the setup, the branch model (pull requests go to `dev`; `master` holds releases)
and how a release is cut, and
[benchmarks/](https://github.com/OussamaMesbah/fundclone/blob/master/benchmarks/README.md)
how to rerun the benchmark. Please follow the
[code of conduct](https://github.com/OussamaMesbah/fundclone/blob/master/CODE_OF_CONDUCT.md)
and report security problems privately, as described in
[SECURITY.md](https://github.com/OussamaMesbah/fundclone/blob/master/SECURITY.md).

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[app,dev]"
pytest
ruff check .
```

The tests run offline on synthetic data, the web app included. Among other things they
check that changing a fund's returns from some date on leaves every earlier clone return
unchanged.

## License and citation

FundClone is released under the [MIT license](https://github.com/OussamaMesbah/fundclone/blob/master/LICENSE). If you use it in research, cite
it with the metadata in [CITATION.cff](https://github.com/OussamaMesbah/fundclone/blob/master/CITATION.cff).

FundClone is a research tool, not investment advice.
