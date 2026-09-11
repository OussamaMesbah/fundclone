# Contributing

Issues and pull requests are welcome.

## Set up

```bash
git clone https://github.com/OussamaMesbah/fundclone.git && cd fundclone
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[app,dev]"
```

## Before you open a pull request

```bash
ruff format .
ruff check .
pytest
```

The tests run offline on synthetic data. A change to how clones are estimated or measured
also needs the benchmark (see [benchmarks/README.md](benchmarks/README.md)): tune on the dev
funds only (`--split dev`) and score the holdout and fresh funds once, at the end. If a
change moves published numbers, update README.md and benchmarks/README.md in the same pull
request.

## The price snapshot

The web app ships with adjusted closes of its ETFs and the benchmark funds
(`data/prices.parquet`) and uses them when Yahoo Finance does not answer. Refresh the
snapshot now and then:

```bash
python -m benchmarks.download --snapshot data/prices.parquet
```

## Releases

1. Set the new version in `pyproject.toml`, `fundclone/__init__.py` and `CITATION.cff` (a
   test checks that they agree), and turn the "Unreleased" heading in `CHANGELOG.md` into
   the version and date.
2. Commit, then tag and push the tag:

   ```bash
   git tag -a v0.4.0 -m "FundClone 0.4.0"
   git push origin v0.4.0
   ```

3. The release workflow runs the tests, checks that the tag matches the version, builds the
   package and creates the GitHub release with the changelog section as its notes. It also
   publishes to PyPI once trusted publishing is set up (environment `pypi`, repository
   variable `PUBLISH_TO_PYPI=true`).
