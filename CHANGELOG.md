# Changelog

## Unreleased

### Changed
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
