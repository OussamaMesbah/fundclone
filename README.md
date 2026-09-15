# FundClone

**Is your active fund worth its fee?** FundClone clones any mutual fund, ETF or
portfolio with a mix of low-cost ETFs, and measures, strictly out of sample, how
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
- **The clone itself.** Usually six to ten liquid ETFs and their weights, what the fees
  add up to and how the mix changed over time; cap it at three or five ETFs for a simpler
  one. Whole-share orders and a CSV show what the weights would mean for an amount, as an
  illustration rather than a recommendation.
- **What switching would cost.** The tax on gains you would realise by selling the fund,
  the tax on the gains the clone's own trading realises, how long the lower fees take to
  earn it back, and a warning for share classes that charge a sales load.
- **For investors in the EU.** 47 UCITS ETFs and a gold ETC on Xetra as a second set of
  building blocks, for funds priced in European hours, and a lookup that finds a European
  fund's Yahoo Finance symbol from its ISIN.
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
American Funds Growth Fd of Amer A (AGTHX), out of sample 2006-08-02 to 2026-09-14

A clone of 11 ETFs explains 98% of the variation in AGTHX's weekly returns out of sample, with a tracking error of 2.4% a year.
The clone costs 0.24% a year in ETF fees; the fund charges 0.59%.
AGTHX returned 0.1% a year less than its clone after all fees; the 95% range is -1.2% to +1.1%, so the gap is within the noise.
The closest single ETF, IWF, tracks with 4.2% tracking error; against it alone, AGTHX returned 1.9% a year less (95% range -3.8% to +0.0%).

Clone as of 2026-09-01:
  IWF    Russell 1000 Growth                  28.4%
  QQQ    Nasdaq-100                           16.0%
  FDN    Internet                             10.3%
  EFG    MSCI EAFE Growth                      8.6%
  ...
note: Class A shares usually charge a front-end sales load, often up to 5.75% for stock funds. ...
```

The web app at [fundclone.streamlit.app](https://fundclone.streamlit.app) shows the same
analysis with charts, the cost of switching and links that carry every setting, such as
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
mutual funds across the same categories, picked once version 0.3 was finished and scored
once with it; version 0.6 changed the fit (below) and was scored on them once more:

| 23 fresh funds, 2010 to 2026 | Median tracking error | Mean tracking error | Median R² | ETFs held |
|---|---|---|---|---|
| The closest single ETF, picked with hindsight | 4.35% | 4.68% | 0.912 | 1 |
| 4-7 hand-picked ETFs, as before 0.3 | 3.41% | 4.37% | 0.930 | 2.9 |
| FundClone 0.3 | 2.79% | 2.85% | 0.970 | 7.8 |
| **FundClone 0.6** | **2.73%** | **2.88%** | **0.968** | **6.8** |
| FundClone 0.6, at most 5 ETFs | 2.88% | 2.96% | 0.966 | 4.5 |

With 23 funds the median itself is uncertain: drawing the funds again and again with
replacement (a bootstrap) puts it between 2.1% and 3.2% with 95% confidence. Compared fund
by fund, the clone tracks 1.20 percentage points more closely than the closest single ETF
in the median (95% range 0.80 to 2.07; more closely on 22 of the 23 funds), and 0.73
points more closely than the hand-picked ETFs (0.35 to 1.13). Both halves of the period
show the same: from 2010 to 2017 the fresh median is 2.40% against 3.31% for the closest
ETF, from 2018 to 2026 3.15% against 5.12%. The 81 ETFs were picked in 2026, with
hindsight; limited to the 68 that were already trading in January 2009, a year before
scoring starts, the median over all 64 funds stays at 2.84%.

Version 0.6 fits the clone on overlapping three-day returns instead of single days, with a
stronger pull towards last month's weights. Daily fund prices that follow the market a
little late had made the clones hold too little risk: the funds' median beta to their
clones was 1.03, which flattered the funds by about 0.2 percentage points a year, and is
now 1.01. The new fit was chosen on the development funds by a rule set before looking at
the results. On the fresh funds it tracks 0.07 points less closely than 0.3 in the median
fund, with one ETF fewer and 12% less trading. Plain least squares on the same 81 ETFs
tracks about as closely (2.70%) but trades more than twice as much and holds 13 ETFs. By
category, over the whole benchmark:

| Category | Funds | Hand-picked ETFs | 0.6 | Example |
|---|---|---|---|---|
| Index funds | 4 | 0.6% | 0.6% | VFIAX 0.6% |
| US large-cap | 15 | 3.8% | 3.0% | AGTHX 2.4% |
| US small/mid-cap | 7 | 4.2% | 3.3% | VEXPX 2.2% |
| International | 10 | 4.4% | 3.5% | HAINX 2.9% |
| Global | 2 | 3.1% | 2.3% | ANWPX 2.4% |
| Balanced | 9 | 2.4% | 1.9% | FBALX 1.6% |
| Bond | 9 | 1.9% | 1.7% | VBTLX 1.1% |
| Sector | 7 | 13.3% | 4.6% | VGHCX 3.7% |
| Single stock | 1 | 11.8% | 10.8% | BRK-B |

What remains is mostly what the manager does that no ETF combination can: picking
individual stocks. For a fund with 2% tracking error that is a small bet; for ARKK (21%)
or Berkshire Hathaway (11%) it is a large part of the story. The protocol, the results for every
fund, a comparison of seven estimation methods and the commands to reproduce every
number are in [benchmarks/](https://github.com/OussamaMesbah/fundclone/blob/master/benchmarks/README.md).

Did the funds beat their clones? Of the benchmark's 59 active funds, 9 returned more than
their clone by more than noise from 2010 to 2026 after fees, and 1 less; the median fund
was 0.33% a year ahead. They are well-known survivors, which flatters them, and most of
the lead dates from 2010 to 2017: from 2018 on, 2 were ahead by more than noise and 2
behind. Against the closest single ETF, 6 were ahead by more than noise and 8 behind, and
the median fund came out level.

## How it works

FundClone builds on returns-based style analysis
([Sharpe, 1992](https://web.stanford.edu/~wfsharpe/art/sa/sa.htm)): a fund's returns are
explained by a long-only mix of asset-class returns. To judge performance, Sharpe
re-estimated that mix every month from the previous 60 months only, and counted what the
fund returned beyond it as selection. FundClone keeps that design and changes the
ingredients: ETFs you can buy instead of asset-class indices, daily returns weighted
towards recent days, a day's delay before trading, and trading costs. It then measures,
out of sample, how closely the clone follows the fund and what the fund returns beyond it.
Every step, with its parameters and references, is in
[docs/method.md](https://github.com/OussamaMesbah/fundclone/blob/master/docs/method.md).

1. **Building blocks.** 81 liquid US-listed ETFs: size and style, the eleven sectors, 16
   industries, factor ETFs, developed and emerging regions, 18 bond ETFs, REITs, gold and
   commodities. ETFs join once they have enough history. For investors in the EU there is
   a second set of 47 UCITS ETFs and ETCs on Xetra, whose euro prices are converted to USD.
2. **Monthly re-estimation.** At each month-end the long-only ETF mix that best follows
   the fund's excess returns over the past 18 months is found by constrained least
   squares, on overlapping three-day sums of daily returns, so that fund prices that
   follow the market a little late do not make the clone too cautious. Recent days count
   more (63-day half-life), weights the data cannot tell apart stay close to last month's,
   and positions below 2% are dropped.
3. **Realistic trading.** The new weights are traded at the next day's close and drift
   with prices until the following month. Every trade pays 5 bp; anything not invested
   sits in T-bills.
4. **Honest measurement.** Tracking error, R² and the fund-minus-clone return are
   computed on weekly out-of-sample returns, and the return gap is the difference in
   compound growth. Its 95% range uses a Newey-West standard error, which widens it when
   a gap tends to carry over from one week to the next. The verdict also sets the fund
   against the closest single ETF, the simplest alternative to it. Before any of this,
   the fund's prices are checked for what goes wrong on Yahoo Finance: prices repeated
   for a day, bad prices that come back, unadjusted splits, and distributions booked a
   day late or not yet (docs/method.md, section 2).
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

## Prior work and related tools

None of the ideas is new. Sharpe (1992) already measured a fund against a style mix
estimated from earlier data only, and Hasanhodzic and Lo (2007) built rolling-window
"linear clones" of hedge funds from liquid factors. Commercial analytics such as Zephyr
StyleADVISOR have offered style analysis for decades, Portfolio Visualizer offers it with
factor regressions and manager performance analysis, and Interactive Brokers gives its
clients a Mutual Fund Replicator that suggests ETFs in place of a mutual fund. What
FundClone adds is narrower: the style mix is made of ETFs you can buy and is traded with
costs, the method is scored on a published benchmark that includes funds picked after
development, and all of it, benchmark included, is open source under the MIT license.

## Limitations

- Stock selection cannot be cloned from returns. For concentrated funds the tracking
  error stays high; that is the size of the active bet you pay for.
- The clone can hold a little less risk than the fund: when the fund's prices follow the
  market late, and when no mix of ETFs moves as much as the fund, since the clone does not
  borrow. On the benchmark the funds' median beta to their clones is 1.01 (1.04 for bond
  funds, whose clones keep about 15% in T-bills), worth about 0.06 percentage points a
  year of the gap in the median; for a fund like ARKK, with a beta of 1.45 to its clone,
  it is much more.
- Investors in the EU generally cannot buy the US-listed ETFs. The UCITS set suits funds
  priced in European hours. For funds priced in US hours its Xetra prices, set four and a
  half hours earlier, add timing noise: over 2018 to 2026 the benchmark's median weekly
  tracking error is 8.0% with UCITS ETFs against 3.2% with US-listed ones, and 8.0%
  against 1.1% for index funds (see benchmarks/).
- The first clone needs about 19 months of prices (18 to fit it), and figures from less
  than a year of out-of-sample returns mean little: the verdict says so and leaves out
  the ESMA screen.
- Prices come from Yahoo Finance through yfinance. They have gaps and errors, and Yahoo's
  terms allow personal, non-commercial use only, so the repository ships no Yahoo data.
  When Yahoo limits requests, FundClone waits, tries again and then says so. Yahoo
  sometimes takes days to adjust a fund's prices for a distribution; when the latest
  prices fall the way a payout does, the figures end the day before, with a note. Its
  coverage of European funds is patchy: many have only a few years of prices, some none,
  and often no expense ratio.
- Every figure follows the fund's net asset value: after its expense ratio, but before any
  sales load and before tax. The app warns for share classes whose name implies a load, and
  turns a load and your own tax situation into numbers, but it knows neither.
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

- UCITS counterparts for the US building blocks, so that the clone of a US fund can be
  bought in the EU.
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
