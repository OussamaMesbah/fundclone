"""Version numbers. The package and pyproject.toml always agree. A release version such as
0.4.0 needs its changelog section; a development version such as 0.5.0.dev0 comes after the
latest release. CITATION.cff always describes the latest release."""

import re
from pathlib import Path

import fundclone

ROOT = Path(__file__).parents[1]
CHANGELOG = (ROOT / "CHANGELOG.md").read_text()
CITATION = (ROOT / "CITATION.cff").read_text()
RELEASE = re.compile(r"\d+\.\d+\.\d+")
DEVELOPMENT = re.compile(r"(\d+\.\d+\.\d+)\.dev\d+")


def pyproject_version() -> str:
    text = (ROOT / "pyproject.toml").read_text()
    return re.search(r'^version = "([^"]+)"', text, re.MULTILINE).group(1)


def citation(field: str) -> str:
    return re.search(rf"^{field}: (\S+)", CITATION, re.MULTILINE).group(1)


def latest_release() -> tuple[str, str]:
    """Version and date of the newest dated release section in the changelog."""
    match = re.search(r"^## (\d+\.\d+\.\d+) \((\d{4}-\d{2}-\d{2})\)", CHANGELOG, re.MULTILINE)
    return match.group(1), match.group(2)


def as_tuple(release: str) -> tuple[int, ...]:
    return tuple(int(part) for part in release.split("."))


def test_the_package_and_pyproject_agree():
    assert fundclone.__version__ == pyproject_version()


def test_the_version_is_a_release_or_a_development_version():
    version = pyproject_version()
    assert RELEASE.fullmatch(version) or DEVELOPMENT.fullmatch(version)


def test_citation_describes_the_latest_release():
    version, date = latest_release()
    assert citation("version") == version
    assert citation("date-released") == date


def test_the_version_matches_the_changelog():
    version = pyproject_version()
    if RELEASE.fullmatch(version):
        assert latest_release()[0] == version
    elif development := DEVELOPMENT.fullmatch(version):
        # A development version comes after the latest release and collects its changes
        # under "Unreleased".
        assert as_tuple(development.group(1)) > as_tuple(latest_release()[0])
        assert "\n## Unreleased\n" in CHANGELOG
