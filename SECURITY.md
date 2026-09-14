# Security policy

## Supported versions

Fixes go into the latest release only.

| Version | Supported |
|---|---|
| 0.5.x | yes |
| older | no |

## Reporting a vulnerability

Please do not open a public issue for a security problem. Report it privately instead:
on the repository's **Security** tab, choose **Report a vulnerability**
([direct link](https://github.com/OussamaMesbah/fundclone/security/advisories/new)). Describe
what an attacker could do, how to reproduce it and which version or deployment is
affected. The maintainer aims to reply within a week and will credit you in the release
notes unless you prefer otherwise.

## Scope

In scope: the `fundclone` package and command, the web app in `streamlit_app.py` and its
deployment at [fundclone.streamlit.app](https://fundclone.streamlit.app), the benchmark
scripts and the GitHub Actions workflows.

Out of scope: the correctness of third-party data from Yahoo Finance or the Kenneth French
data library, and the investment merit of any result. FundClone is a research tool, not
investment advice.

## How the project handles secrets

FundClone needs no API keys, passwords or other credentials, and the web app reads no
Streamlit secrets. The workflows run with a read-only `GITHUB_TOKEN` unless a job states
otherwise (creating a release needs write access to contents), and publishing to PyPI uses
trusted publishing, so no PyPI token is stored anywhere. Secret scanning with push
protection, Dependabot alerts and security updates, and CodeQL code scanning are enabled
for the repository.
