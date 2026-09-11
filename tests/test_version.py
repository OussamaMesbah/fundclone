"""The version is set in three places; a release needs them to agree."""

import re
from pathlib import Path

import fundclone

ROOT = Path(__file__).parents[1]


def pyproject_version() -> str:
    text = (ROOT / "pyproject.toml").read_text()
    return re.search(r'^version = "([^"]+)"', text, re.MULTILINE).group(1)


def test_versions_agree():
    citation = re.search(r"^version: (\S+)", (ROOT / "CITATION.cff").read_text(), re.MULTILINE)
    assert fundclone.__version__ == pyproject_version() == citation.group(1)


def test_the_changelog_has_a_section_for_the_version():
    changelog = (ROOT / "CHANGELOG.md").read_text()
    assert f"\n## {pyproject_version()} (" in changelog
