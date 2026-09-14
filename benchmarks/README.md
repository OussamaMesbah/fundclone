# Benchmark

How closely can a portfolio of ETFs follow a mutual fund when it is built only from
information available at the time? This benchmark measures it on 62 US mutual funds, one
ETF and, as a control, one stock. It is the evidence behind the numbers in the
[main README](../README.md).

## Protocol

- **Funds.** [funds.csv](funds.csv) lists two sets.
  - *Development set* (41): 10 US large-cap, 4 small/mid-cap, 6 international, 1 global,
    6 bond, 6 balanced and 4 sector funds (one of them ARK Innovation, an ETF), 3 index
    funds and Berkshire Hathaway as a single-stock control. Before any tuning they were
    split alternately within each category into a dev half (21 funds) and a holdout half
    (20). Methods and settings were tuned on the dev half only. The holdout half was
    looked at during development, though: all 41 funds were scored with an earlier,
    smaller ETF list before the industry and further bond ETFs were added, and each of
    the seven finalists of the estimator comparison below was scored on it before the
    final design was chosen. It is out of sample in time, but not an untouched holdout.
  - *Fresh set* (23): 5 US large-cap, 3 small/mid-cap, 4 international (one of them an
    emerging markets fund), 1 global, 3 bond, 3 balanced and 3 sector funds and 1 index
    fund. They were picked from well-known funds in each category once development was
    finished, and run once with the final code. This is the clean test.
- **Period.** Clones are scored from January 2010, or three years after a younger fund's
  first price, to September 2026. Estimation data start in 2006.
- **Clone.** At each month-end the estimator receives the trailing window of daily excess
  returns over T-bills for the fund and for every ETF with a full window, and returns
  long-only weights that sum to at most one; the rest is cash. The weights are traded at
  the next day's close, drift with prices until the next rebalance and pay 5 bp of traded
  value.
- **Metrics.** Tracking error is the annualised standard deviation of weekly
  fund-minus-clone returns; R² is 1 − var(fund − clone) / var(fund) on the same weekly
  returns. Turnover is traded value per calendar year as a multiple of the portfolio,
  and "ETFs" the average number of positions above 1%. The CSVs also hold daily and
  monthly tracking error.
- **Data.** Adjusted closes from Yahoo Finance and the daily T-bill rate from the Kenneth
  French data library, as of 11 September 2026. Where a fund's price did not change on a
  day when it should have moved (its beta to the median ETF times that day's median ETF
  return exceeds 0.4%), the day is merged with the next. In funds whose typical daily
  move is below 1.9%, a price that jumps by more than 15% while the market is calm and
  returns to within 3% of its earlier level within five days is dropped; in this
  snapshot that catches one bad price, BSCFX on 4 January 2010. A jump that does not
  reverse and matches a split ratio is undone as an unadjusted split; there is none in
  this snapshot.
- **Baseline.** "Before 0.3" fits plain least squares on 252 days to a fixed set of four
  to seven ETFs per type of fund (`LEGACY` in [run.py](run.py)) on raw prices. That is
  how the project, then called FactorLens, worked before version 0.3; its public version
  0.1.0 also used a few hand-picked ETFs per type of fund, though not exactly these.

## Results

Fresh set, 23 funds, run once:

| Version | Median tracking error | Mean tracking error | Median R² | Turnover | ETFs |
|---|---|---|---|---|---|
| Before 0.3: 4-7 hand-picked ETFs, least squares on 252 days | 3.78% | 4.44% | 0.930 | 0.75 | 2.9 |
| 81 ETFs, least squares on 252 days | 2.84% | 2.87% | 0.966 | 2.62 | 13.0 |
| **FundClone 0.3** | **2.89%** | **2.92%** | **0.966** | **1.30** | **7.8** |
| FundClone 0.3, at most 5 ETFs | 3.00% | 3.02% | 0.963 | 1.54 | 4.6 |

With this few funds the medians are uncertain. A bootstrap over the funds (10,000 draws,
printed by `benchmarks.run`) puts the fresh median of 0.3 at 2.29% to 3.19% (95%) and the
one before 0.3 at 3.09% to 4.37%. The two ranges overlap; fund by fund, though, 0.3 tracks
more closely on 22 of the 23 funds, by 0.54 percentage points in the median (95% range
0.25 to 1.31).

Holdout half of the development set, 20 funds:

| Version | Median tracking error | Mean tracking error | Median R² | Turnover | ETFs |
|---|---|---|---|---|---|
| Before 0.3 | 3.37% | 4.84% | 0.935 | 0.83 | 2.8 |
| 81 ETFs, least squares on 252 days | 2.82% | 3.24% | 0.958 | 2.79 | 12.1 |
| **FundClone 0.3** | **2.86%** | **3.28%** | **0.958** | **1.21** | **7.5** |
| FundClone 0.3, at most 5 ETFs | 2.95% | 3.43% | 0.954 | 1.52 | 4.6 |

The whole development set, 41 funds:

| Version | Median tracking error | Mean tracking error | Median R² | Turnover | ETFs |
|---|---|---|---|---|---|
| Before 0.3 | 3.66% | 5.07% | 0.928 | 0.85 | 3.0 |
| 81 ETFs, least squares on 252 days | 2.95% | 3.48% | 0.961 | 2.97 | 13.4 |
| **FundClone 0.3** | **2.93%** | **3.50%** | **0.960** | **1.23** | **8.0** |
| FundClone 0.3, at most 5 ETFs | 3.05% | 3.66% | 0.954 | 1.66 | 4.7 |

The wider set of building blocks does most of the work: the median tracking error of the
seven sector funds fell from 13.3% with the hand-picked ETFs to 6.5% with every ETF but
the 16 industry ETFs, and to 4.6% with those added. They took the semiconductor fund
FSELX from 14.4% to 6.6% and the biotech fund FBIOX from 15.9% to 5.4%. The new estimator matches plain least squares on the development
set (2.93% against 2.95%) with 59% less turnover and 41% fewer positions. On the fresh
set it tracks slightly less closely (2.89% against 2.84%) with half the turnover.
Version 0.3 tracks more closely than the baseline on 61 of the 64 funds. The exceptions
are three broad US index funds, where four ETFs already do a near-perfect job: VFIAX
0.62% against 0.64%, VTSAX 0.54% against 0.64% and FXAIX 0.60% against 0.63%.

### Every fund

| Fund | Category | Set | Before | 0.3 | R² (0.3) | ETFs | Turnover |
|---|---|---|---|---|---|---|---|
| FXAIX | Index | fresh | 0.60% | 0.63% | 0.999 | 5.7 | 0.32 |
| VTSAX | Index | holdout | 0.54% | 0.64% | 0.999 | 5.3 | 0.26 |
| VFIAX | Index | dev | 0.62% | 0.64% | 0.998 | 5.1 | 0.29 |
| VGTSX | Index | dev | 2.23% | 1.70% | 0.989 | 9.4 | 1.17 |
| VWNFX | US large-cap | holdout | 2.36% | 2.00% | 0.984 | 8.7 | 1.06 |
| AGTHX | US large-cap | holdout | 3.32% | 2.19% | 0.984 | 10.7 | 1.36 |
| AIVSX | US large-cap | holdout | 2.74% | 2.28% | 0.977 | 9.1 | 1.23 |
| VDIGX | US large-cap | fresh | 4.37% | 2.65% | 0.965 | 6.8 | 1.00 |
| AWSHX | US large-cap | fresh | 3.33% | 2.93% | 0.961 | 9.1 | 1.24 |
| FCNTX | US large-cap | dev | 3.66% | 2.96% | 0.969 | 7.2 | 1.15 |
| TRBCX | US large-cap | holdout | 4.00% | 3.00% | 0.976 | 6.8 | 1.19 |
| PRGFX | US large-cap | fresh | 4.04% | 3.07% | 0.974 | 6.6 | 1.13 |
| DODGX | US large-cap | dev | 4.28% | 3.17% | 0.968 | 10.3 | 1.69 |
| FMAGX | US large-cap | holdout | 3.80% | 3.20% | 0.968 | 9.1 | 1.43 |
| PRBLX | US large-cap | dev | 3.61% | 3.30% | 0.952 | 10.5 | 1.84 |
| AMCPX | US large-cap | fresh | 3.89% | 3.37% | 0.959 | 10.7 | 1.70 |
| VPMCX | US large-cap | dev | 4.91% | 3.38% | 0.960 | 11.6 | 1.70 |
| FDGRX | US large-cap | fresh | 5.52% | 3.41% | 0.972 | 8.1 | 1.39 |
| OAKMX | US large-cap | dev | 5.14% | 3.47% | 0.965 | 10.2 | 1.59 |
| VEXPX | US small/mid-cap | dev | 3.62% | 2.15% | 0.989 | 6.0 | 0.80 |
| RPMGX | US small/mid-cap | fresh | 4.61% | 2.89% | 0.972 | 7.2 | 1.30 |
| FLPSX | US small/mid-cap | dev | 4.10% | 2.93% | 0.965 | 11.5 | 1.77 |
| PENNX | US small/mid-cap | holdout | 4.19% | 3.19% | 0.975 | 8.0 | 1.28 |
| TRMCX | US small/mid-cap | fresh | 4.19% | 3.19% | 0.966 | 9.3 | 1.66 |
| PRNHX | US small/mid-cap | fresh | 7.44% | 4.66% | 0.947 | 7.1 | 1.47 |
| BSCFX | US small/mid-cap | holdout | 6.42% | 4.85% | 0.945 | 7.3 | 1.74 |
| TROSX | International | fresh | 2.37% | 2.12% | 0.984 | 10.0 | 1.42 |
| FDIVX | International | fresh | 3.78% | 2.79% | 0.972 | 8.7 | 1.64 |
| VTRIX | International | fresh | 3.42% | 2.88% | 0.972 | 9.8 | 1.60 |
| HAINX | International | holdout | 3.42% | 2.98% | 0.971 | 8.0 | 1.49 |
| AEPGX | International | holdout | 3.99% | 3.31% | 0.960 | 10.0 | 2.16 |
| ARTKX | International | dev | 4.92% | 4.15% | 0.930 | 10.5 | 2.32 |
| DODFX | International | dev | 5.39% | 4.21% | 0.949 | 9.9 | 2.36 |
| VWIGX | International | dev | 6.83% | 4.55% | 0.946 | 9.7 | 1.84 |
| ODMAX | International | fresh | 5.66% | 5.54% | 0.901 | 9.0 | 2.47 |
| OAKIX | International | holdout | 8.41% | 6.90% | 0.892 | 7.5 | 2.50 |
| CWGIX | Global | fresh | 2.54% | 2.29% | 0.978 | 12.3 | 1.84 |
| ANWPX | Global | dev | 3.71% | 2.31% | 0.980 | 10.8 | 1.71 |
| FBALX | Balanced | dev | 1.60% | 1.32% | 0.987 | 7.4 | 0.60 |
| RPBAX | Balanced | fresh | 1.47% | 1.38% | 0.984 | 7.8 | 0.52 |
| VWINX | Balanced | holdout | 2.59% | 1.62% | 0.941 | 7.3 | 0.56 |
| VWELX | Balanced | dev | 2.09% | 1.71% | 0.974 | 8.8 | 0.76 |
| AMECX | Balanced | fresh | 3.09% | 1.78% | 0.970 | 9.5 | 1.11 |
| ABALX | Balanced | holdout | 1.91% | 1.81% | 0.969 | 8.7 | 0.84 |
| FPURX | Balanced | fresh | 2.45% | 1.99% | 0.970 | 9.1 | 1.01 |
| DODBX | Balanced | dev | 4.15% | 2.48% | 0.960 | 9.7 | 1.23 |
| PRWCX | Balanced | holdout | 2.94% | 2.74% | 0.937 | 8.6 | 1.19 |
| VBTLX | Bond | holdout | 1.30% | 1.22% | 0.924 | 5.8 | 0.26 |
| DODIX | Bond | holdout | 1.63% | 1.50% | 0.871 | 5.6 | 0.35 |
| TGLMX | Bond | fresh | 1.73% | 1.56% | 0.886 | 4.0 | 0.31 |
| MWTRX | Bond | dev | 1.90% | 1.56% | 0.894 | 6.2 | 0.43 |
| PTTRX | Bond | dev | 1.90% | 1.78% | 0.861 | 6.7 | 0.60 |
| DBLTX | Bond | fresh | 1.99% | 1.91% | 0.792 | 3.3 | 0.23 |
| FTBFX | Bond | dev | 2.39% | 2.25% | 0.777 | 7.7 | 0.52 |
| LSBRX | Bond | holdout | 3.05% | 2.42% | 0.821 | 7.5 | 0.98 |
| PIMIX | Bond | fresh | 3.24% | 3.17% | 0.539 | 6.0 | 0.83 |
| VGHCX | Sector | holdout | 9.70% | 3.69% | 0.943 | 6.5 | 1.24 |
| PRHSX | Sector | fresh | 11.04% | 3.91% | 0.955 | 6.1 | 1.38 |
| FSPTX | Sector | fresh | 7.99% | 4.47% | 0.960 | 5.9 | 1.31 |
| VGENX | Sector | fresh | 13.31% | 4.55% | 0.957 | 6.3 | 1.16 |
| FBIOX | Sector | holdout | 18.60% | 5.37% | 0.955 | 3.3 | 0.96 |
| FSELX | Sector | dev | 16.88% | 6.58% | 0.948 | 2.7 | 0.81 |
| ARKK | Sector | dev | 27.33% | 21.26% | 0.736 | 4.1 | 2.39 |
| BRK-B | Single stock | holdout | 11.80% | 10.75% | 0.645 | 7.0 | 2.62 |

## Is the list of ETFs chosen with hindsight?

The 81 ETFs were picked in 2026 from those that are liquid today, a list nobody could have
known in 2010. A clone never uses an ETF's prices before the ETF existed: an ETF joins only
once it has a full estimation window. But the list leaves out ETFs that have closed since
and favours those that became popular. As a check, the benchmark was rerun with only the
68 ETFs that already traded on 2 January 2009, a year before scoring starts
(`--universe traded-by:2009-01-02`). The 13 dropped are XLRE, XLC, MTUM, QUAL, USMV,
VLUE, INDA, VCSH, VCIT, FLOT, BKLN, CWB and BNDX. On a snapshot of 14 September 2026,
which reproduces the published medians:

| ETFs | Median tracking error, 64 funds | Mean tracking error | Fresh set median |
|---|---|---|---|
| All 81 | 2.91% | 3.30% | 2.89% |
| The 68 that traded by January 2009 | 2.91% | 3.33% | 2.88% |

Fund by fund, the tracking error rises by 0.01 percentage points in the median (95% range
0.00 to 0.03). The largest change is Fidelity Contrafund's, from 2.97% to 3.29%. Choosing
the ETFs with hindsight therefore barely flatters the results. ETFs that have closed
cannot be tested, because Yahoo Finance no longer has their prices.

## Why tracking error does not go much lower

**Daily prices are noisy.** SPY and IVV, two ETFs that hold the same S&P 500 stocks,
differ by 0.86% a year on daily returns since 2010 but by only 0.45% on weekly returns,
and the daily gap reverses the next day (lag-one autocorrelation about −0.5): it is
noise in closing prices, not tracking error. Between the Vanguard 500 Index Fund and SPY
the figures are 1.03% and 0.52%. On top of that, Yahoo's daily mutual fund prices are
sometimes stale, the previous price repeated and the move arriving a day later. That is
why the benchmark reports weekly figures and merges stale days.

**Stock selection cannot be cloned.** Seven quite different estimators ended up within
0.15 percentage points of each other (next section). If better estimation could close
much of the gap, some of them would have. What remains is the part of the fund's return
that no combination of the 81 ETFs spans: the manager's individual stock bets. For
Berkshire Hathaway, a single company, it is about a third of the weekly variance
(out-of-sample R² 0.65), enough to keep the tracking error near 11%.

## Choosing the estimator

Seven AI coding agents (Claude), working in parallel, each built and tuned one estimator
on the dev funds only. For each entry a separate agent then checked the code for
look-ahead and for state carried between funds, confirmed the dev figures and ran it
once on the holdout funds. The final design below was the author's choice. At that stage the
benchmark measured daily tracking error on raw prices, with turnover per 252 trading
days, so these figures are not directly comparable with the tables above.

| Estimator | Dev median | Dev mean | Dev turnover | Holdout median | Holdout mean | Holdout turnover |
|---|---|---|---|---|---|---|
| Least squares on 252 days (reference) | 3.02% | 3.99% | 3.12 | 3.12% | 3.79% | 2.80 |
| Least squares on 378 days (lower turnover) | 3.07% | 4.01% | 2.26 | 3.11% | 3.79% | 2.05 |
| Exponentially weighted, prior on last month's weights | 2.95% | 3.97% | 2.80 | 3.00% | 3.74% | 2.41 |
| Ridge towards last month's weights | 2.95% | 3.95% | 1.89 | 3.02% | 3.73% | 1.62 |
| Average of seven window lengths, moved 70% of the way from last month's weights | 2.98% | 3.96% | 2.50 | 2.99% | 3.74% | 2.30 |
| Kalman filter on the weights | 2.98% | 3.96% | 1.46 | 2.98% | 3.73% | 1.39 |
| Robust ensemble of half-lives with a prior | 2.98% | 3.94% | 1.94 | 2.97% | 3.74% | 1.81 |
| Greedy forward selection | 3.01% | 3.99% | 3.42 | 3.12% | 3.76% | 3.01 |

On the holdout funds the medians differ by at most 15 basis points and the means by less
than 7, while turnover differs by more than a factor of two. FundClone therefore uses the
simplest low-turnover design, the ridge towards last month's weights with recent days
weighted more, and adds a 2% minimum position so that the clone has no holdings too small
to matter. On the dev funds, with the current benchmark:

| Variant (dev funds) | Median tracking error | Mean tracking error | Turnover | ETFs |
|---|---|---|---|---|
| Least squares on 252 days | 2.95% | 3.70% | 3.15 | 13.5 |
| Ridge, no minimum position | 2.90% | 3.67% | 1.89 | 15.0 |
| **Ridge, 2% minimum position (default)** | **2.93%** | **3.71%** | **1.23** | **9.4** |
| Ridge, 3% minimum position | 2.97% | 3.81% | 0.92 | 6.2 |
| Forward selection, at most 8 ETFs | 3.04% | 3.80% | 1.99 | 6.6 |
| Forward selection, at most 5 ETFs | 3.05% | 3.88% | 1.84 | 4.8 |
| Forward selection, at most 3 ETFs | 3.10% | 4.08% | 1.20 | 3.0 |
| Ridge, 2% minimum, overlapping 3-day returns | 2.94% | 3.68% | 1.51 | 9.0 |
| Ridge, 2% minimum, overlapping 5-day returns | 2.98% | 3.72% | 1.73 | 8.9 |

Dropping small positions after the fit gives a simpler clone at lower cost than selecting
ETFs one by one: with about the same number of ETFs, a 3% minimum tracks about as closely
as a cap of eight (median 2.97% against 3.04%, mean 3.81% against 3.80%) and trades half
as much. Fitting on
overlapping multi-day returns, which the literature suggests for funds priced at
different hours, did not help on these funds.

## Reproduce

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[app,dev]"
python -m benchmarks.download                                                   # writes benchmarks/data

python -m benchmarks.run --split fresh --window 378 --estimator product         # FundClone 0.3, fresh set
python -m benchmarks.run --split dev,holdout --window 378 --estimator product   # development set
python -m benchmarks.run --split all --window 378 --estimator product --max-etfs 5
python -m benchmarks.run --split all                                             # least squares, 81 ETFs
python -m benchmarks.run --split all --universe legacy --raw                     # the baseline
python -m benchmarks.run --split all --window 378 --estimator product --universe traded-by:2009-01-02
```

Add `--out results.csv` to keep the per-fund rows. Yahoo revises its history now and
then, so a fresh snapshot moves the figures slightly.

## Try your own estimator

Write a function `estimate(y, X, previous, config)` in a file. It receives the fund's
excess returns `y` over the window, those of the available ETFs `X`, and the weights it
returned last month, and must return long-only weights that sum to at most one. Keep it a
pure function: the harness runs several funds in one process. Then:

```bash
python -m benchmarks.run --split dev --estimator my_estimator.py:estimate
```

Tune on `--split dev`, and look at the holdout and fresh funds once, at the end.
