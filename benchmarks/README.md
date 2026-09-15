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
    fund. They were picked from well-known funds in each category once version 0.3 was
    finished, and scored once with it. Version 0.6 changed the fit, chosen on the dev
    funds by a rule fixed in advance (see Choosing the estimator), and the holdout and
    fresh funds were then scored once more. This is the clean test, with one limit: they
    are other funds, not other years, scored over the same period on which the settings
    were tuned. Scoring the two halves of the period separately checks that (Results).
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
  monthly tracking error, the gap to the clone and to the closest single ETF with their
  95% ranges, and the gains the clone's sales realise each year.
- **Data.** Adjusted closes from Yahoo Finance and the daily T-bill rate from the Kenneth
  French data library, as of 14 September 2026. Where a fund's price did not change on a
  day when it should have moved (its beta to the median ETF times that day's median ETF
  return exceeds 0.4%), the day is merged with the next. In funds whose typical daily
  move is below 1.9%, a price that jumps by more than 15% while the market is calm and
  returns to within 3% of its earlier level within five days is dropped; in this
  snapshot that catches one bad price, BSCFX on 4 January 2010. A jump that does not
  reverse and matches a split ratio is undone as an unadjusted split; there is none in
  this snapshot. A return that breaks away from the fund's most correlated ETF by more
  than 4% and comes back within two days is dropped: here AMCPX and AWSHX on 19 December
  2014, when Yahoo booked a distribution a day late, FBIOX's stale prices of 6 and 7 May
  2025, and VWIGX on 29 September 2008, priced hours before the crash day's close. A drop
  among a fund's last ten returns that its most correlated ETF does not explain and that
  does not come back looks like a distribution Yahoo has not adjusted for yet, and the
  fund's figures end the day before. In this snapshot that is FLPSX, whose price fell 8.7%
  on 11 September with no distribution listed; without the check its tracking error would
  be 3.70%, not 2.93%.
- **Baseline.** "Before 0.3" fits plain least squares on 252 days to a fixed set of four
  to seven ETFs per type of fund (`LEGACY` in [run.py](run.py)), on the same cleaned
  prices as every other row. That is how the project, then called FactorLens, worked
  before version 0.3, which fitted raw prices; its public version 0.1.0 also used a few
  hand-picked ETFs per type of fund, though not exactly these.

## Results

All figures come from the snapshot of 14 September 2026. Fresh set, 23 funds, scored once
with 0.3 and once with 0.6:

| Version | Median tracking error | Mean tracking error | Median R² | Turnover | ETFs |
|---|---|---|---|---|---|
| The closest single ETF, picked with hindsight | 4.35% | 4.68% | 0.912 | 0 | 1 |
| Before 0.3: 4-7 hand-picked ETFs, least squares on 252 days | 3.41% | 4.37% | 0.930 | 0.73 | 2.9 |
| 81 ETFs, least squares on 252 days | 2.70% | 2.80% | 0.971 | 2.62 | 13.0 |
| FundClone 0.3 | 2.79% | 2.85% | 0.970 | 1.30 | 7.8 |
| **FundClone 0.6** | **2.73%** | **2.88%** | **0.968** | **1.14** | **6.8** |
| FundClone 0.6, at most 5 ETFs | 2.88% | 2.96% | 0.966 | 1.55 | 4.5 |

With this few funds the medians are uncertain. A bootstrap over the funds (10,000 draws,
printed by `benchmarks.run`) puts the fresh median of 0.6 at 2.09% to 3.24% (95%) and the
one before 0.3 at 2.65% to 4.37%. The two ranges overlap; fund by fund, though, 0.6 tracks
more closely on 22 of the 23 funds, by 0.73 percentage points in the median (95% range
0.35 to 1.13, printed by `benchmarks.compare`). Against the closest single ETF, picked
with hindsight as in the app's verdict, it tracks more closely on 22 of the 23 funds, by
1.20 points in the median (0.80 to 2.07), and on 62 of all 64 funds, by 1.24 points (1.11
to 1.78). Against 0.3 it gives up a little: 0.07 points on the median fresh fund (−0.08
to 0.00) and 0.01 on the median holdout fund, for clones that hold the right amount of
risk (see [Did the funds beat their clones?](#did-the-funds-beat-their-clones)).

Scored separately, the two halves of the period rank the versions the same way. Median
tracking error of the fresh funds:

| Fresh set | 2010 to 2017 | 2018 to 2026 |
|---|---|---|
| The closest single ETF | 3.31% | 5.12% |
| Before 0.3 | 2.94% | 3.90% |
| **FundClone 0.6** | **2.40%** | **3.15%** |

Holdout half of the development set, 20 funds:

| Version | Median tracking error | Mean tracking error | Median R² | Turnover | ETFs |
|---|---|---|---|---|---|
| The closest single ETF, picked with hindsight | 4.39% | 4.77% | 0.909 | 0 | 1 |
| Before 0.3 | 3.37% | 4.82% | 0.936 | 0.82 | 2.8 |
| 81 ETFs, least squares on 252 days | 2.82% | 3.24% | 0.959 | 2.79 | 12.1 |
| FundClone 0.3 | 2.86% | 3.28% | 0.958 | 1.21 | 7.5 |
| **FundClone 0.6** | **2.89%** | **3.26%** | **0.960** | **1.11** | **7.2** |
| FundClone 0.6, at most 5 ETFs | 2.94% | 3.33% | 0.959 | 1.41 | 4.5 |

The whole development set, 41 funds:

| Version | Median tracking error | Mean tracking error | Median R² | Turnover | ETFs |
|---|---|---|---|---|---|
| The closest single ETF, picked with hindsight | 4.71% | 5.05% | 0.907 | 0 | 1 |
| Before 0.3 | 3.66% | 5.06% | 0.929 | 0.83 | 3.0 |
| 81 ETFs, least squares on 252 days | 2.95% | 3.47% | 0.962 | 2.97 | 13.4 |
| FundClone 0.3 | 2.93% | 3.50% | 0.960 | 1.23 | 8.0 |
| **FundClone 0.6** | **2.93%** | **3.48%** | **0.960** | **1.11** | **7.2** |
| FundClone 0.6, at most 5 ETFs | 3.04% | 3.59% | 0.954 | 1.48 | 4.6 |

The wider set of building blocks does most of the work: the median tracking error of the
seven sector funds fell from 13.3% with the hand-picked ETFs to 6.5% with every ETF but
the 16 industry ETFs, and to 4.6% with those added. They took the semiconductor fund
FSELX from 14.4% to 6.6% and the biotech fund FBIOX from 15.9% to 5.4%. The estimator
matches plain least squares on the development set (2.93% against 2.95%) with 63% less
turnover and 46% fewer positions; on the fresh set it tracks slightly less closely (2.73%
against 2.70%) with 56% less turnover. Version 0.6 tracks more closely than the baseline
on 61 of the 64 funds. The exceptions are two balanced funds and a total-market index
fund, where a few ETFs already do very well: ABALX 1.94% against 1.91%, RPBAX 1.55%
against 1.31% and VTSAX 0.61% against 0.51%.

### Every fund

| Fund | Category | Set | Before | 0.6 | R² (0.6) | ETFs | Turnover |
|---|---|---|---|---|---|---|---|
| FXAIX | Index | fresh | 0.60% | 0.57% | 0.999 | 5.1 | 0.17 |
| VFIAX | Index | dev | 0.60% | 0.60% | 0.999 | 4.6 | 0.17 |
| VTSAX | Index | holdout | 0.51% | 0.61% | 0.999 | 6.0 | 0.24 |
| VGTSX | Index | dev | 2.21% | 1.53% | 0.991 | 7.3 | 0.52 |
| VWNFX | US large-cap | holdout | 2.36% | 2.07% | 0.983 | 7.2 | 0.75 |
| AWSHX | US large-cap | fresh | 2.65% | 2.09% | 0.980 | 7.5 | 0.82 |
| AIVSX | US large-cap | holdout | 2.74% | 2.37% | 0.976 | 10.1 | 1.17 |
| AGTHX | US large-cap | holdout | 3.32% | 2.38% | 0.981 | 10.0 | 1.16 |
| AMCPX | US large-cap | fresh | 3.36% | 2.62% | 0.975 | 9.9 | 1.22 |
| VDIGX | US large-cap | fresh | 4.37% | 2.72% | 0.963 | 6.2 | 0.88 |
| FCNTX | US large-cap | dev | 3.66% | 2.99% | 0.969 | 6.6 | 0.96 |
| TRBCX | US large-cap | holdout | 3.99% | 3.04% | 0.975 | 6.6 | 1.04 |
| PRGFX | US large-cap | fresh | 4.04% | 3.24% | 0.971 | 6.6 | 1.18 |
| DODGX | US large-cap | dev | 4.29% | 3.25% | 0.967 | 9.8 | 1.50 |
| FMAGX | US large-cap | holdout | 3.79% | 3.35% | 0.965 | 8.2 | 1.28 |
| PRBLX | US large-cap | dev | 3.62% | 3.40% | 0.949 | 10.2 | 1.64 |
| VPMCX | US large-cap | dev | 4.90% | 3.42% | 0.959 | 11.2 | 1.58 |
| FDGRX | US large-cap | fresh | 5.52% | 3.46% | 0.971 | 7.7 | 1.25 |
| OAKMX | US large-cap | dev | 5.15% | 3.53% | 0.964 | 9.8 | 1.46 |
| VEXPX | US small/mid-cap | dev | 3.62% | 2.17% | 0.989 | 5.5 | 0.64 |
| FLPSX | US small/mid-cap | dev | 4.10% | 2.93% | 0.965 | 10.8 | 1.50 |
| RPMGX | US small/mid-cap | fresh | 4.60% | 3.00% | 0.970 | 6.8 | 1.18 |
| TRMCX | US small/mid-cap | fresh | 4.17% | 3.26% | 0.964 | 7.4 | 1.27 |
| PENNX | US small/mid-cap | holdout | 4.18% | 3.28% | 0.973 | 7.5 | 1.13 |
| PRNHX | US small/mid-cap | fresh | 7.43% | 4.75% | 0.945 | 7.2 | 1.48 |
| BSCFX | US small/mid-cap | holdout | 6.33% | 4.81% | 0.945 | 7.4 | 1.64 |
| TROSX | International | fresh | 2.37% | 2.09% | 0.985 | 7.4 | 0.74 |
| FDIVX | International | fresh | 3.77% | 2.73% | 0.974 | 7.7 | 1.19 |
| VTRIX | International | fresh | 3.41% | 2.84% | 0.973 | 9.1 | 1.14 |
| HAINX | International | holdout | 3.41% | 2.95% | 0.971 | 7.3 | 1.14 |
| AEPGX | International | holdout | 3.96% | 3.07% | 0.966 | 8.7 | 1.33 |
| ARTKX | International | dev | 4.93% | 3.93% | 0.937 | 9.4 | 1.72 |
| DODFX | International | dev | 5.40% | 3.94% | 0.956 | 8.4 | 1.54 |
| VWIGX | International | dev | 6.83% | 4.54% | 0.947 | 8.8 | 1.55 |
| ODMAX | International | fresh | 5.65% | 5.31% | 0.909 | 8.2 | 1.92 |
| OAKIX | International | holdout | 8.40% | 6.47% | 0.905 | 6.9 | 1.95 |
| CWGIX | Global | fresh | 2.52% | 2.26% | 0.978 | 11.0 | 1.19 |
| ANWPX | Global | dev | 3.71% | 2.38% | 0.979 | 9.4 | 1.24 |
| RPBAX | Balanced | fresh | 1.31% | 1.55% | 0.980 | 6.4 | 0.45 |
| VWINX | Balanced | holdout | 2.58% | 1.56% | 0.946 | 7.2 | 0.48 |
| FBALX | Balanced | dev | 1.61% | 1.57% | 0.982 | 7.2 | 0.63 |
| VWELX | Balanced | dev | 2.08% | 1.77% | 0.973 | 7.2 | 0.62 |
| ABALX | Balanced | holdout | 1.91% | 1.94% | 0.965 | 7.4 | 0.68 |
| AMECX | Balanced | fresh | 3.10% | 1.96% | 0.964 | 9.3 | 0.86 |
| FPURX | Balanced | fresh | 2.44% | 2.05% | 0.968 | 6.7 | 0.64 |
| DODBX | Balanced | dev | 4.14% | 2.47% | 0.960 | 8.2 | 1.05 |
| PRWCX | Balanced | holdout | 2.93% | 2.84% | 0.933 | 9.1 | 1.11 |
| VBTLX | Bond | holdout | 1.29% | 1.12% | 0.936 | 6.2 | 0.23 |
| DODIX | Bond | holdout | 1.63% | 1.22% | 0.916 | 3.6 | 0.23 |
| MWTRX | Bond | dev | 1.84% | 1.61% | 0.886 | 5.7 | 0.31 |
| TGLMX | Bond | fresh | 1.69% | 1.68% | 0.867 | 3.5 | 0.23 |
| PTTRX | Bond | dev | 1.89% | 1.69% | 0.876 | 6.5 | 0.43 |
| DBLTX | Bond | fresh | 1.98% | 1.92% | 0.789 | 4.2 | 0.23 |
| FTBFX | Bond | dev | 2.39% | 2.15% | 0.798 | 6.3 | 0.37 |
| LSBRX | Bond | holdout | 3.04% | 2.24% | 0.847 | 6.4 | 0.73 |
| PIMIX | Bond | fresh | 3.24% | 2.90% | 0.614 | 4.9 | 0.62 |
| VGHCX | Sector | holdout | 9.70% | 3.69% | 0.943 | 5.8 | 1.11 |
| PRHSX | Sector | fresh | 11.05% | 3.99% | 0.953 | 6.1 | 1.28 |
| FSPTX | Sector | fresh | 8.00% | 4.57% | 0.958 | 5.8 | 1.18 |
| VGENX | Sector | fresh | 13.32% | 4.65% | 0.955 | 6.0 | 1.11 |
| FBIOX | Sector | holdout | 18.61% | 5.39% | 0.955 | 3.1 | 0.83 |
| FSELX | Sector | dev | 16.88% | 6.63% | 0.947 | 3.0 | 0.88 |
| ARKK | Sector | dev | 27.29% | 21.11% | 0.740 | 3.9 | 2.35 |
| BRK-B | Single stock | holdout | 11.79% | 10.80% | 0.642 | 6.7 | 2.60 |

## Did the funds beat their clones?

The benchmark's 59 active funds, that is all but the index funds and Berkshire Hathaway,
after all fees, as the app's verdict would put it. A fund is ahead or behind by more than
noise when the 95% range of its gap excludes zero:

| Against | Scored | Ahead | Ahead by more than noise | Behind by more than noise | Median gap a year |
|---|---|---|---|---|---|
| Its clone | 2010 to 2026 | 35 | 9 | 1 | +0.33% |
| Its clone | 2010 to 2017 | 41 | 14 | 0 | +0.62% |
| Its clone | 2018 to 2026 | 28 | 2 | 2 | −0.13% |
| The closest single ETF | 2010 to 2026 | 29 | 6 | 8 | −0.02% |
| The closest single ETF | 2010 to 2017 | 34 | 9 | 2 | +0.31% |
| The closest single ETF | 2018 to 2026 | 23 | 1 | 2 | −0.48% |

The funds were picked because they are well known today, so they are survivors, and
survivors tend to have done well; their lead dates from the years before 2018. The closest
single ETF, the simplest thing an investor could have bought instead, is picked with
hindsight as the one that tracked best, not as the one that returned most.

Up to 0.5 the clones held a little too little risk, which tilted the comparison with the
clone towards the funds. They kept a median 3% in T-bills (13% for bond funds), and the
funds' weekly beta to their clone was 1.03 in the median (1.10 for bond funds). Daily fund
prices, especially those of bond funds, which are set from evaluated quotes, follow the
market a little late, so a fit on single days sees the fund as less sensitive to the ETFs
than it is. Index funds, whose prices move in step with the ETFs, showed nothing of the
kind (99% invested, beta 1.00). The missing risk was worth about 0.2 percentage points a
year of the median gap.

Version 0.6 fits overlapping three-day returns, which absorb late prices. The median beta
of the funds to their clones is now 1.01, between 1.01 and 1.02 on each of the dev,
holdout and fresh sets, and the missing risk is worth about 0.06 points a year. What
remains sits where the clone cannot follow: bond funds (beta 1.04, with about 15% of their
clones in T-bills) and funds that move more than any mix of ETFs, which the clone would
have to borrow for, such as ARKK (beta 1.45). Measured as alpha against the clone,
allowing for the beta, 9 funds are ahead by more than noise and 1 behind.

## Is the list of ETFs chosen with hindsight?

The 81 ETFs were picked in 2026 from those that are liquid today, a list nobody could have
known in 2010. A clone never uses an ETF's prices before the ETF existed: an ETF joins only
once it has a full estimation window. But the list leaves out ETFs that have closed since
and favours those that became popular. As a check, the benchmark was rerun with only the
68 ETFs that already traded on 2 January 2009, a year before scoring starts
(`--universe traded-by:2009-01-02`). The 13 dropped are XLRE, XLC, MTUM, QUAL, USMV,
VLUE, INDA, VCSH, VCIT, FLOT, BKLN, CWB and BNDX.

| ETFs | Median tracking error, 64 funds | Mean tracking error | Fresh set median |
|---|---|---|---|
| All 81 | 2.84% | 3.27% | 2.73% |
| The 68 that traded by January 2009 | 2.84% | 3.30% | 2.78% |

Fund by fund, the tracking error rises by 0.01 percentage points in the median (95% range
0.00 to 0.02). The largest change is Fidelity Contrafund's, from 2.99% to 3.28%. Choosing
the ETFs with hindsight therefore barely flatters the results. ETFs that have closed
cannot be tested, because Yahoo Finance no longer has their prices.

## UCITS ETFs and funds priced in US hours

FundClone also offers 47 UCITS ETFs on Xetra, for investors in the EU (`--etf-set UCITS`).
Their prices are set when Xetra closes, four and a half hours before US funds are priced,
and converted to USD with an exchange rate taken at yet another time. For US funds that
adds noise that has nothing to do with how well the ETFs match the fund: the S&P 500 UCITS
ETF SXR8, converted to USD, differs from SPY by 7.8% a year on weekly returns and 4.0% on
monthly returns since 2018. Its daily return correlates 0.50 with SPY's on the same day and
0.32 with SPY's on the day before.

All 64 funds, scored from January 2018 (when most UCITS sector ETFs have a full estimation
window), fitted on weekly returns:

| Building blocks | Median weekly tracking error | Median monthly tracking error | Median R² |
|---|---|---|---|
| 81 US-listed ETFs | 3.21% | 3.14% | 0.959 |
| 47 UCITS ETFs on Xetra | 8.03% | 4.78% | 0.783 |

UCITS ETFs track less closely on every one of the 64 funds, by 4.67 percentage points in
the median. The index funds show that it is timing: with UCITS ETFs on the same indices,
their median weekly tracking error is 8.03% against 1.07%. For funds priced in European
hours the timing works the other way. Fundsmith Equity, a London fund (not in the
benchmark; run on 15 September 2026), is cloned with 9.2% weekly tracking error and an R²
of 0.64 from UCITS ETFs, against 10.9% and 0.51 from US-listed ETFs; it holds about 25
stocks, so neither set gets close. The analysis therefore points to the UCITS ETFs for
funds priced in European hours and warns when they are chosen for a fund priced in US
hours.

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
(out-of-sample R² 0.64), enough to keep the tracking error near 11%.

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
to matter. On the dev funds, with the benchmark as it was for 0.3:

| Variant (dev funds) | Median tracking error | Mean tracking error | Turnover | ETFs |
|---|---|---|---|---|
| Least squares on 252 days | 2.95% | 3.70% | 3.15 | 13.5 |
| Ridge, no minimum position | 2.90% | 3.67% | 1.89 | 15.0 |
| **Ridge, 2% minimum position (0.3 to 0.5)** | **2.93%** | **3.71%** | **1.23** | **9.4** |
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
different hours, did not lower the tracking error on these funds, though it removes most
of the clones' missing risk (next section).

### Clones with the right amount of risk (0.6)

Up to 0.5 the clones held too little risk (see
[Did the funds beat their clones?](#did-the-funds-beat-their-clones)). After a first look
at three-day, five-day and weekly fits, and before the other variants were run, the rule
for choosing was fixed: among the variants that bring the median beta of the dev funds to
their clones within 0.01 of one, take the one with the lowest median tracking error, and
among those within 0.02 points of it the one that trades least. "Pull" is the penalty
that keeps weights close to last month's ($\lambda$ in [docs/method.md](../docs/method.md)).
On the dev funds only, before the check for prices that come back was added:

| Variant (dev funds) | Median tracking error | Mean tracking error | Turnover | ETFs | Median beta to the clone |
|---|---|---|---|---|---|
| Single days, pull 0.1 (0.3 to 0.5) | 2.93% | 3.71% | 1.23 | 9.4 | 1.038 |
| Single days, weights scaled by the fund's beta to the clone | 2.93% | 3.72% | 1.27 | 9.2 | 1.023 |
| Overlapping 2-day returns, pull 0.1 | 2.90% | 3.66% | 1.38 | 9.1 | 1.018 |
| Overlapping 3-day returns, pull 0.1 | 2.94% | 3.68% | 1.51 | 9.0 | 1.009 |
| Overlapping 5-day returns, pull 0.1 | 2.98% | 3.72% | 1.73 | 8.9 | 1.001 |
| Weekly returns, pull 0.1 | 3.11% | 3.90% | – | – | 0.998 |
| **Overlapping 3-day returns, pull 0.2 (0.6)** | **2.93%** | **3.69%** | **1.05** | **7.3** | **1.010** |
| Overlapping 3-day returns, pull 0.3 | 2.92% | 3.72% | 0.78 | 6.7 | 1.012 |
| Overlapping 5-day returns, pull 0.2 | 3.01% | 3.77% | 1.17 | 8.3 | 1.003 |
| Overlapping 5-day returns, pull 0.3 | 3.05% | 3.78% | 0.92 | 7.9 | 1.002 |

The winner tracks the dev funds as closely as before, trades less, holds fewer ETFs and
brings the beta from 1.04 to 1.01. The holdout and fresh funds were then scored once
(tables above).

## Reproduce

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[app,dev]"
python -m benchmarks.download                                                   # writes benchmarks/data

python -m benchmarks.run --split fresh --window 378 --estimator product         # FundClone 0.6, fresh set
python -m benchmarks.run --split dev,holdout --window 378 --estimator product   # development set
python -m benchmarks.run --split all --window 378 --estimator product --max-etfs 5
python -m benchmarks.run --split all                                             # least squares, 81 ETFs
python -m benchmarks.run --split all --universe legacy                           # the baseline
python -m benchmarks.run --split all --window 378 --estimator product --eval-end 2017-12-29     # first half
python -m benchmarks.run --split all --window 378 --estimator product --eval-start 2018-01-02  # second half
python -m benchmarks.run --split all --window 378 --estimator product --universe traded-by:2009-01-02
python -m benchmarks.run --split all --window 378 --estimator product --eval-start 2018-01-02 --frequency weekly
python -m benchmarks.run --split all --window 378 --estimator product --eval-start 2018-01-02 --frequency weekly --etf-set UCITS
```

FundClone 0.3 is `--overlap 1` with `STABILITY = 0.1` in `fundclone/estimators.py`. Add
`--out results.csv` to keep the per-fund rows. Yahoo revises its history now and then, so
a fresh snapshot moves the figures slightly. Two such files give the fund-by-fund
comparisons, a median difference with its bootstrap range:

```bash
python -m benchmarks.run --split all --window 378 --estimator product --out product.csv
python -m benchmarks.run --split all --universe legacy --out before.csv
python -m benchmarks.compare before.csv product.csv --split fresh               # before 0.3 minus 0.6
python -m benchmarks.compare product.csv product.csv --column te_closest --second-column te_weekly --split fresh
```

The last line sets the closest single ETF against the clone, fund by fund.

## Try your own estimator

Write a function `estimate(y, X, previous, config)` in a file. It receives the fund's
excess returns `y` over the window, those of the available ETFs `X`, and the weights it
returned last month, and must return long-only weights that sum to at most one. Keep it a
pure function: the harness runs several funds in one process. Then:

```bash
python -m benchmarks.run --split dev --estimator my_estimator.py:estimate
```

Tune on `--split dev`, and look at the holdout and fresh funds once, at the end.
