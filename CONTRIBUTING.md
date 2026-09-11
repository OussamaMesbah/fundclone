# Contributing

Issues and pull requests are welcome. Please follow the [code of conduct](CODE_OF_CONDUCT.md),
and report security problems privately as described in [SECURITY.md](SECURITY.md).

## Set up

```bash
git clone https://github.com/OussamaMesbah/fundclone.git && cd fundclone
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[app,dev]"
```

## Branches

- `master` holds released code. The web app deploys from it, and every release is tagged on
  it. It is protected: changes arrive only through pull requests that pass CI.
- `dev` collects the changes for the next release. Branch off `dev` (or fork the
  repository), and open your pull request against `dev`. Pull requests into `dev` are
  squash-merged, so one pull request becomes one commit.
- A release is a pull request from `dev` into `master`, merged with a merge commit, followed
  by a tag (see below).

Neither branch accepts force pushes or can be deleted.

## Before you open a pull request

```bash
ruff format .
ruff check .
pytest
```

CI runs the same checks on Python 3.10 and 3.13 and builds the package. The tests run
offline on synthetic data. Add a test for new behaviour, and an entry under "Unreleased" in
[CHANGELOG.md](CHANGELOG.md) for anything users will notice.

A change to how clones are estimated or measured also needs the benchmark (see
[benchmarks/README.md](benchmarks/README.md)): tune on the dev funds only (`--split dev`) and
score the holdout and fresh funds once, at the end. If a change moves published numbers,
update README.md and benchmarks/README.md in the same pull request.

## Dependencies

The web app on Streamlit Community Cloud installs the exact versions in
`requirements.txt`. After changing dependencies in `pyproject.toml`, regenerate it:

```bash
uv pip compile pyproject.toml --extra app --python-version 3.12 -o requirements.txt
```

Dependabot proposes updates for it and for the GitHub Actions once a month.

## A local price snapshot

Yahoo Finance data may not be redistributed, so the repository contains none. A self-hosted
deployment can still fall back on a snapshot of its own when Yahoo does not answer: build
one for personal use, and the app picks it up from `data/prices.parquet` (ignored by git) or
from the path in the environment variable `FUNDCLONE_SNAPSHOT`.

```bash
python -m benchmarks.download --snapshot data/prices.parquet
```

## Releases

1. On `dev`, set the new version in `pyproject.toml`, `fundclone/__init__.py` and
   `CITATION.cff` (a test checks that they agree), set `date-released` in `CITATION.cff`,
   and turn the "Unreleased" heading in `CHANGELOG.md` into the version and date.
2. Optionally run the release workflow as a dry run: `gh workflow run release.yml --ref dev`.
3. Open a pull request from `dev` into `master` and merge it with a merge commit once CI
   passes.
4. Tag `master` and push the tag:

   ```bash
   git switch master && git pull
   git tag -a v0.4.0 -m "FundClone 0.4.0"
   git push origin v0.4.0
   ```

5. The release workflow runs the tests, checks that the tag matches the version, builds the
   package and creates the GitHub release with the changelog section as its notes. It also
   publishes to PyPI once trusted publishing is set up (environment `pypi`, repository
   variable `PUBLISH_TO_PYPI=true`).
