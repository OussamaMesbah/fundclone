# Changelog

## Unreleased

### Added
- The benchmark reports the closest single ETF of every fund, as the app's verdict does, and
  how many active funds came out ahead of or behind their clone and that ETF after fees, by
  more than noise or not, over the whole period or any part of it (`--eval-end`). The
  README and benchmarks/README.md report the result.
- An expense ratio can be entered where Yahoo Finance reports none or an outdated one, as
  for many European funds: in the app, in links (`ter=1.5`), on the command line
  (`--expense-ratio 1.5`) and in Python (`expense_ratio=0.015`).
- The ISIN lookup shows how many prices Yahoo has for each symbol and since when, lists
  those with enough for a clone first, and searches by the fund's name when no listing has
  prices.
- "Switching from the fund" shows the tax on the gains the clone's own trading realises,
  at average cost over its first years out of sample, when it starts with no gains as
  someone switching now would. Like the tax on selling the fund and on the fund's own
  capital-gain distributions, it is mostly paid earlier rather than extra, so it is shown
  beside the payback rather than in it.
- `benchmarks.compare` compares two benchmark runs fund by fund, with a bootstrap range for
  the median difference, so the README's fund-by-fund figures can be reproduced.
- A check for distributions Yahoo Finance has not adjusted for yet. When one of a fund's
  last ten returns falls the way a payout does and does not come back, the figures end the
  day before, with a note. FLPSX's price fell 8.7% this way on 11 September 2026, and Yahoo
  listed no distribution.

### Changed
- The clone is fitted on overlapping three-day returns, with a stronger pull towards last
  month's weights. Daily fund prices that follow the market a little late had made the
  clones hold too little risk, which flattered the funds by about 0.2 points a year: the
  funds' median beta to their clones falls from 1.03 to 1.01 on the benchmark. Clones hold
  7 ETFs instead of 8 and trade about 10% less, for about the same tracking error (0.07
  points more on the median fresh fund). The fit was chosen on the dev funds by a rule set
  in advance, and every published number is rescored on the snapshot of 14 September 2026.
- The benchmark's baseline, the hand-picked ETFs used before 0.3, is fitted to the same
  cleaned prices as everything else instead of raw prices.
- "Switching from the fund" no longer counts a front-end load already paid as a saving
  from switching: it is gone whether or not the fund is sold, so it now counts only for new
  money. A deferred sales charge still due on selling is part of the cost of switching.
- The README describes the clone and its orders as the app does: whole-share orders and the
  CSV are an illustration, not a recommendation.

### Fixed
- Prices that break away from the fund's closest ETF and come back within two days are
  left out: distributions Yahoo books a day late (AMCPX and AWSHX on 19 December 2014) and
  prices that stay unchanged while the market moves (FBIOX in May 2025).
- While Yahoo limits requests, looking up a fund's name, currency and fees is retried, then
  falls back to an earlier lookup and otherwise says so, instead of reading a fund of
  unknown currency as priced in dollars. A self-hosted app with a price snapshot still
  works while Yahoo limits every request.
- The README, docs/method.md and the app's Method tab said Sharpe (1992) fitted the style
  mix once, over the whole history. To measure performance he re-estimated it every month
  from the previous 60 months. They now say so, credit Hasanhodzic and Lo (2007) for
  rolling-window clones, and say what FundClone changes: ETFs you can buy, daily returns
  and trading costs.

## 0.5.0 (2026-09-14)

Answers to the points a critical reader would raise, and UCITS building blocks for
investors in the EU. How clones are estimated is unchanged, so the benchmark results of
0.3.0 still hold; the verdict's 95% ranges now allow for gaps that carry over from week to
week.

### Added
- UCITS building blocks for investors in the EU: 47 UCITS ETFs and a gold ETC on Xetra with
  ISINs and total expense ratios, chosen as the ETF set in the app (`?set=UCITS`), on the
  command line (`--etf-set UCITS`) and in the benchmark. Their euro prices are converted
  to USD, and known errors in Yahoo's Xetra prices are left out. The analysis points to
  them for funds priced in European hours and warns that their Xetra prices add timing
  noise for funds priced in US hours.
- A lookup that lists the Yahoo Finance symbols for an ISIN, also for the ISINs found in a
  factsheet, as candidates to check.
- The benchmark can start scoring at a later date (`--eval-start`) and runs on either ETF
  set.
- The verdict also sets the fund against the closest single ETF, with a 95% range: how
  much the fund returned beyond one simple ETF.
- What switching costs: a warning for share classes whose name implies a sales load, the
  tax on gains realised by selling the fund, how long the lower fees take to earn it back,
  and the clone's trading against the turnover the fund reports.
- [docs/method.md](docs/method.md): every step of the method with its parameters, formulas
  and references.
- When Yahoo Finance limits requests, the download waits and tries twice more. If the limit
  lasts, earlier prices are used with a note, or the app and the command line say that
  Yahoo is limiting requests instead of reporting missing data.
- The benchmark reports a bootstrap range for its median tracking error, and can limit the
  ETFs to those already trading at a date (`--universe traded-by:2009-01-02`). Limited to
  the 68 ETFs that traded by January 2009, the median over all 64 funds stays at 2.91%.

### Changed
- The 95% range of the fund-minus-clone gap uses a Newey-West standard error, so it
  widens when a gap tends to carry over from one week to the next.
- The whole-share orders and the CSV sit in an "Illustrative orders" section of their own,
  marked as an illustration rather than a recommendation.
- The README and the app's Method tab credit returns-based style analysis (Sharpe, 1992),
  on which the clone builds, and say what FundClone adds to it: monthly refits from past
  data only, ETFs you can buy, and out-of-sample measurement after trading costs.

## 0.4.0 (2026-09-11)

Security hardening and a setup for outside contributors. How clones are estimated and
measured is unchanged, so the benchmark results of 0.3.0 still hold.

### Added
- A security policy, a code of conduct, issue and pull-request templates, and a
  `fundclone --version` flag.
- A `dev` branch for upcoming changes; `master` is protected and takes only pull requests
  that pass CI.
- A dry-run mode for the release workflow, started by hand on a branch. Only tags run the
  jobs that can write: the GitHub release and PyPI.
- A visible disclaimer and data attribution in the app and the README, and a privacy note
  for factsheet uploads.

### Changed
- Factsheets are read with pdfminer.six instead of pdfplumber, which sets up every page of
  a file even when only the first few are read.

### Fixed
- The command that builds a local price snapshot creates its folder.
- The release workflow can be rerun, for example after a failed upload to PyPI. It
  uploads the files to the existing GitHub release instead of failing to create it.

### Security
- Text from links, uploads and data sources is shown as plain text, and tickers in links
  are checked, so a crafted link cannot put its own links on the page.
- Factsheet PDFs are read in a separate process with limits on size, time and processor
  time, and on memory on Linux, where the hosted app runs. Only their first five pages are
  opened.
- Portfolios have at most 30 holdings and weights must be ordinary numbers. The caches in
  memory and on disk keep a fixed number of entries, and failed downloads are retried for
  a few tickers only.
- Cache paths built from user input must stay inside the cache folder.
- The workflows pin their actions to commit SHAs and do not keep the checkout token, and
  the web app's dependencies are pinned in requirements.txt.

### Removed
- The Yahoo Finance price snapshot in `data/`: Yahoo's data may not be redistributed.
  Self-hosted deployments can build their own for personal use.

## 0.3.0 (2026-09-11)

Renamed from FactorLens to FundClone (package and command `fundclone`, web app at
fundclone.streamlit.app) and rebuilt around one question: can a handful of low-cost ETFs
do what this fund does, and what does the manager add after fees?

### Added
- Clone any mutual fund, ETF or stock, or a custom portfolio such as `VTI 60, BND 40`,
  from 81 liquid US-listed ETFs: size and style, sectors, industries, factors, regions,
  bonds, gold and commodities.
- A verdict: out-of-sample tracking error and R², the gap in compound growth between
  fund and clone after fees with a 95% range, the clone's expense ratio against the
  fund's, and the closet-indexing thresholds of an ESMA working paper.
- A clone you can buy: current weights, whole-share orders for an amount, fees over a
  horizon and a CSV export. An optional cap on the number of ETFs.
- Links that carry every setting (`?ticker=AGTHX&start=2015-01-01&etfs=5`).
- An out-of-sample benchmark on 64 funds: 41 used during development and 23 fresh ones
  run once with the final code. It comes with a download script for the data snapshot
  and a hook for trying other estimators (`benchmarks/`).
- Data checks: stale mutual fund prices are merged with the following day; for funds and
  ETFs, price errors that reverse within days are dropped and unadjusted splits undone.
- The verdict needs a year of out-of-sample returns for the 95% range, the annualised
  gap and the ESMA screen, and says so when there is less.
- A disk cache for prices, fund facts and factor files, and a price snapshot the web app
  falls back on when Yahoo Finance does not answer.
- Continuous integration on Python 3.10 and 3.13 (tests, lint, package build), a release
  workflow driven by tags and this changelog, and a contributing guide.

### Changed
- New default estimator: recency-weighted constrained least squares with a pull towards
  last month's weights and a 2% minimum position. It came out of a comparison of seven
  approaches whose median tracking errors differed by at most 0.15 percentage points;
  compared with plain least squares it trades about half as much for about the same
  tracking error.
- Tracking statistics are measured on weekly returns, and annual figures on calendar
  time.
- Funds listed or quoted outside the US are fitted on weekly returns.
- Factor attribution picks its region and bond factors from what the clone holds, and is
  left out with a note when the history is too short for it.
- The command line reports input errors in one line instead of a traceback, and reads
  portfolios such as `VTI 60 BND 40`.

### Removed
- The hand-picked ETF universes. Similar sets are the benchmark's baseline.
- The Flask app and its templates.

## 0.1.0

First public version, as FactorLens: factor regression on long-only ETFs and a replicating portfolio,
with a Flask and a Streamlit front end.
