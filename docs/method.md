# How FundClone works

FundClone builds on returns-based style analysis (Sharpe, 1992): a fund's returns are
explained by a long-only mix of asset-class returns. To measure performance, Sharpe
re-estimated the mix each month from the previous 60 months, so that the benchmark for a
month used only earlier data, and called the fund's return beyond it selection.
Hasanhodzic and Lo (2007) applied the same rolling-window idea to hedge funds and called
the result a linear clone. FundClone keeps the design and changes the ingredients: ETFs
that can be bought instead of asset-class indices, daily returns over 18 months weighted
towards recent days, a day's delay before trading, and trading costs. It holds the
result until the next month and measures how closely it followed the fund and what the
fund returned beyond it. This document lists every step with the parameters the code
uses. The benchmark behind the published numbers is described in
[benchmarks/README.md](../benchmarks/README.md).

## 1. Data

- **Prices.** Split- and dividend-adjusted daily closes from Yahoo Finance through
  yfinance, cached on disk for 12 hours. When Yahoo limits requests, the download waits 2
  and then 5 seconds and tries again; after that it uses an earlier download with a note,
  or says that Yahoo is limiting requests (`fundclone/data.py`).
- **Fund facts.** Name, currency, exchange time zone, quote type, net expense ratio and
  reported holdings turnover, from Yahoo Finance, cached for a week.
- **T-bill rate and factors.** The daily one-month T-bill rate and the factor returns come
  from the Kenneth French data library.
- **Currencies.** Prices quoted in another currency are converted to USD with Yahoo's daily
  exchange rate, carrying the last known rate forward. Minor units (GBp, ZAc, ILA) map to
  their major currency.

## 2. Cleaning the fund's prices

These checks apply to funds and ETFs; single stocks and other volatile series are left
alone, because their jumps are often real.

- **Stale prices.** Yahoo sometimes repeats a mutual fund's previous price and catches up a
  day later. The move to expect on a day is the fund's beta to the median reference ETF,
  estimated over the previous 252 days, times that day's median ETF return. A day on which
  the price did not change although that expected move exceeds 0.4% is merged with the
  following day.
- **Data errors.** In a series whose typical daily move is at most 15% / 8 (about 1.9%), a
  move of more than 15% on a day when the median ETF moved less than a quarter as much,
  followed within five days by a return to within 3% of the earlier level, is a data error
  (such as a misplaced decimal point), and the prices in between are dropped.
- **Unadjusted splits.** A move of more than 45% that does not reverse and matches a split
  ratio (2, 3, 4, 5, 8, 10, 15, 20, 25, 30, 40, 50 or 100, or its inverse) is undone as an
  unadjusted split. Other large unreversed moves are reported and left in.
- **Prices that break away and come back.** A return that differs from what the most
  correlated ETF predicts by more than 4% and more than eight typical deviations, and that
  the next two returns undo by at least 80%, is dropped, which merges the days. This
  catches distributions Yahoo books a day late (AMCPX and AWSHX on 19 December 2014: −5%,
  then +6%), prices that stay unchanged for two days while the market moves (FBIOX in May
  2025), and fund prices set hours before a crash day's close (VWIGX on 29 September
  2008). In the benchmark's snapshot these five prices are all it drops.
- **Distributions Yahoo has not adjusted yet.** On the day a fund pays out, its price falls
  by the amount paid. Yahoo sometimes takes days to adjust the earlier prices, or does not
  list the distribution at all. If one of the last ten returns falls short of what the
  most correlated ETF predicts (with the fund's beta to it over the previous year) by more
  than 3% and more than eight typical deviations, and the following days do not undo half
  of it, the figures end the day before.

Every change appears as a note in the app and on the command line.

## 3. The building blocks

81 liquid US-listed ETFs in eight groups (`fundclone/etfs.py`): US equity by size and style
(12), the eleven sectors (11), industries (16), factors (4), international equity (10),
emerging markets (7), bonds (18) and real assets (3). Their net expense ratios are as of
September 2026. At a rebalance, an ETF is eligible only if it has returns over the whole
estimation window, so a clone never uses an ETF before it had enough history.

For investors in the EU, a second set holds 47 UCITS ETFs and a gold ETC on Xetra in ten
groups: world, US, European, Asia-Pacific and emerging-market equity, world factors, world
sectors, euro bonds, global bonds and real assets. Their ISINs and total expense ratios come
from justETF (14 September 2026). Their euro prices are converted to USD with Yahoo's
exchange rate, and the fit uses weekly returns, because they trade in European hours. A
scan of every series found a few errors in Yahoo's Xetra prices: mis-scaled or stale
quotes after a listing, and single days that jump by 13-16% and reverse while the market
is flat. They are listed in `DATA_FROM` and `BAD_DAYS` in `fundclone/etfs.py` and left out.

For the region of the factor model, each equity group counts with its share of US stocks:
1 for US groups, 0 for other regions, and about 0.7, the US weight of the MSCI World, for
world groups.

The UCITS set suits funds priced in European hours. A fund priced at the US close moves
for four and a half hours after Xetra has closed: an S&P 500 ETF on Xetra, converted to
USD, differs from SPY by 7.8% a year on weekly returns. On the benchmark over 2018 to
2026 the median weekly tracking error is 8.0% with UCITS ETFs against 3.2% with US-listed
ones, so the analysis says so when UCITS ETFs are chosen for a fund priced in US hours,
and points to them for a fund priced in European hours.

## 4. The walk-forward clone

- **Signal dates.** The last trading day of each month (or quarter), once the estimation
  window is full.
- **Window.** The past 378 trading days, about 18 months.
- **Returns.** Daily excess returns over the T-bill rate, summed over overlapping
  three-day spans (days 1 to 3, 2 to 4, and so on). On single days, a fund whose price
  follows the market a little late, as bond and international funds' often do, looks less
  sensitive to the ETFs than it is, and the clone then holds too little risk; three-day
  sums absorb most of that (see benchmarks/README.md). When the fund or the ETFs are
  priced outside US trading hours, as the UCITS ETFs on Xetra are, weekly returns (weeks
  ending on Friday) instead, which absorb much of the timing mismatch.
- **Estimator.** With $y_t$ the fund's excess return, $x_t$ the ETFs' excess returns and
  $w_{\text{prev}}$ last month's weights, the weights solve

  $$\min_{w \ge 0,\ \sum_i w_i \le 1} \ \frac{1}{T\,u} \sum_{t=1}^{T} \rho_t \left(y_t - x_t^\top w\right)^2 + \lambda \left\lVert w - w_{\text{prev}} \right\rVert^2$$

  where $\rho_t = 0.5^{a_t / 63}$, normalised to a mean of one, weights an observation
  $a_t$ trading days old (a 63-day half-life), $u$ is the average ETF variance, and
  $\lambda = 0.2$, in units of that variance, pulls weights that the data cannot tell
  apart towards last month's. The penalty applies once there is a previous clone. The rest,
  $1 - \sum_i w_i$, is held in T-bills. The problem is solved as one non-negative least
  squares problem with a slack column for cash and a heavily weighted row for the budget
  (`fundclone/estimators.py`).
- **Minimum position.** Positions below 2% are dropped and the rest refitted, up to three
  times.
- **Capped clones.** With at most $k$ ETFs, forward selection adds one ETF at a time: of
  the eight most correlated with the current residual, the one that lowers the error most.
  ETFs held last month get a 25% bonus, so the selection does not flip between
  near-equivalent ETFs, and selection stops once another ETF improves the fit by less than
  0.1%.
- **Long/short or levered clones** (Python API only) use plain constrained least squares.

## 5. Trading and costs

Weights estimated with data through day $t$ are traded at the close of day $t+1$ and first
earn returns on day $t+2$. Between trades the positions drift with prices, cash earns the
T-bill rate, and every trade pays 5 basis points of the traded value. Turnover is the
traded value, buys and sells, as a multiple of the portfolio (`fundclone/replication.py`).

## 6. Measurement

All tracking figures use weekly returns (weeks ending on Friday) over the out-of-sample
period, because daily closing prices of funds carry timing noise that is not tracking
error.

- **Tracking error.** $\sigma(f - c)\sqrt{52}$, with $f$ and $c$ the weekly returns of fund
  and clone.
- **Explained share.** $R^2 = 1 - \operatorname{var}(f - c) / \operatorname{var}(f)$. Out of
  sample it can be negative.
- **Growth and gap.** Each series grows at $g = \exp\left(52 \cdot \overline{\log(1 + r)}\right) - 1$
  a year, and the gap is $g_f - g_c$: the difference in compound growth, which unlike the
  mean of $f - c$ does not favour the more volatile series.
- **95% range of the gap.** With $\ell = 52 \cdot \overline{\log(1+f) - \log(1+c)}$ the
  annualised mean log gap over $n$ weeks, its standard error is
  $s = 52 \sqrt{\hat\Omega / n}$, where $\hat\Omega$ is the Newey-West (1987) long-run
  variance of the weekly log gap with Bartlett weights and
  $L = \lfloor 4 (n/100)^{2/9} \rfloor$ lags (Newey and West, 1994), 6 for 16 years of
  weeks. It widens the range when a gap tends to carry over from week to week. The range
  is $(1 + g_c)\left(\exp(\ell \pm t_{0.975,\,n-1}\, s) - 1\right)$ (`fundclone/metrics.py`,
  `fundclone/report.py`).
- **Short samples.** With fewer than 52 weeks, or less than a calendar year, of
  out-of-sample returns, the verdict shows no annual gap, no range and no closet-index
  screen.
- **The closest single ETF.** The ETF with the lowest weekly tracking error against the fund
  over the same weeks. Its gap and range are computed the same way. It is chosen with
  hindsight, which flatters the ETF rather than the fund.
- **Closet-index screen.** For clones that are at least 70% equity: tracking error below
  3%, $R^2$ above 95% (the squared correlation) and beta between 0.95 and 1.05 against the
  closest single ETF. The thresholds come from an ESMA working paper (Danieli, Harris and
  Pichini, 2020), which applied them year by year, to figures from monthly returns, against
  each fund's own benchmark. FundClone applies them once, to all weekly out-of-sample
  returns.

## 7. Factor attribution

Monthly excess returns (daily on request) are regressed on the market, size, value,
profitability and investment factors (Fama and French, 2015) and momentum (Carhart, 1997).
The region of the factors follows the clone's equity: Developed ex US if more than 80% of
it is international, Developed if more than 35%, US otherwise or if the clone is less than
20% equity. When bonds are more than 25% of the clone, term (IEF minus the T-bill rate)
and credit (LQD minus IEF) factors are added, after Fama and French (1993). The regression
is ordinary least squares with Newey-West standard errors and the same lag rule. Loading
times mean factor return, plus alpha, splits the mean excess return; rolling loadings use
36-month windows (`fundclone/attribution.py`).

## 8. Costs outside the returns

The fund's returns follow its net asset value: after its expense ratio, but before any
sales load and before tax (`fundclone/costs.py`).

- **Fees over a horizon.** On an amount $A$ growing 6% a year before fees, an expense ratio
  $e$ takes $A \cdot 1.06^Y \left(1 - (1 - e)^Y\right)$ over $Y$ years.
- **Sales loads.** Yahoo Finance reports none, so the app warns when a share class name
  implies one (Class A, C or T). For new money, a load $l$ paid once costs
  $1 - (1 - l)^{1/Y}$ a year over $Y$ years: 5.75% over ten years is 0.59% a year. Money
  already in the fund has paid its load, which is gone whether or not the fund is sold, so
  it plays no part in switching.
- **Switching.** Selling the fund realises gains $A \cdot G$ and costs $A \cdot G \cdot \tau$
  in tax at a rate $\tau$, plus $A \cdot d$ where a deferred sales charge $d$ is still due.
  The yearly saving is $A$ times the fund's expense ratio minus the clone's, less the tax
  at the same rate on the gains the clone's own trading realised out of sample, with each
  ETF's average cost as its basis (a median 6.6% of its value a year on the benchmark).
  The cost takes cost over saving years to earn back. Most of the tax on selling is paid
  earlier rather than extra, since selling later would owe it too; in a tax-deferred
  account there is none. The fund's own capital-gain distributions are taxed too, but
  Yahoo Finance does not report them reliably, so they are left out, which leans against
  the clone.
- **Trading.** The app sets the clone's turnover, with buys and sells counted once each,
  against the turnover the fund reports.

## 9. What guards the out-of-sample claim

- `tests/test_replication.py` checks that changing a fund's returns from some date on
  leaves every earlier clone return unchanged, that weekly fits stay causal, that ETFs
  join only with a full window, and that only returns after the first trade are reported.
- The benchmark scored 23 funds picked after version 0.3 was finished, once with its code
  and once more with 0.6, whose fit was chosen on the dev funds by a rule fixed in
  advance. It reports bootstrap ranges for its medians, `benchmarks.compare` gives them
  for fund-by-fund comparisons, and a rerun limited to the 68 ETFs that already traded in
  January 2009 leaves the median tracking error unchanged.
- The fresh funds are other funds, not other years: the settings were tuned on the dev
  funds over the same period. Seven quite different estimators ended within 0.15
  percentage points of each other, so the settings matter little, and scoring 2010 to
  2017 and 2018 to 2026 separately gives the same ranking (the clone tracks more closely
  than the hand-picked ETFs and than the closest single ETF in both), but only data after
  September 2026 can test other years.

## 10. Limitations

Stock selection cannot be cloned from returns; the clone can hold a little less risk than
the fund where no mix of ETFs moves as much (the median beta of the benchmark's funds to
their clones is 1.01, but 1.04 for bond funds), which flatters the fund in rising
markets; UCITS ETFs suit only funds priced in
European hours; the ETF list was
picked in 2026 and closed ETFs are missing from it; only funds that still exist can be
analysed; Yahoo Finance data has gaps and errors and is licensed for personal use; the
French factors lag by one to two months and are paper portfolios. The
[README](../README.md#limitations) has the full list.

## References

- Carhart, M. M. (1997). On persistence in mutual fund performance. *Journal of Finance*,
  52(1), 57–82.
- Danieli, L., Harris, A., and Pichini, G. (2020). *Closet indexing indicators and investor
  outcomes*. ESMA Working Paper No. 2, 2020.
  [PDF](https://www.esma.europa.eu/sites/default/files/library/esmawp-2020-2_closet_indexing.pdf)
- Fama, E. F., and French, K. R. (1993). Common risk factors in the returns on stocks and
  bonds. *Journal of Financial Economics*, 33(1), 3–56.
- Fama, E. F., and French, K. R. (2015). A five-factor asset pricing model. *Journal of
  Financial Economics*, 116(1), 1–22.
- Hasanhodzic, J., and Lo, A. W. (2007). Can hedge-fund returns be replicated?: The linear
  case. *Journal of Investment Management*, 5(2), 5–45.
- Newey, W. K., and West, K. D. (1987). A simple, positive semi-definite, heteroskedasticity
  and autocorrelation consistent covariance matrix. *Econometrica*, 55(3), 703–708.
- Newey, W. K., and West, K. D. (1994). Automatic lag selection in covariance matrix
  estimation. *Review of Economic Studies*, 61(4), 631–653.
- Sharpe, W. F. (1992). Asset allocation: Management style and performance measurement.
  *Journal of Portfolio Management*, 18(2), 7–19.
  [Article](https://web.stanford.edu/~wfsharpe/art/sa/sa.htm)
