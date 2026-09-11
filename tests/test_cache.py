"""Cache paths come from user input (tickers in the web app's URL) and must stay in the cache."""

import pytest

from fundclone import data


@pytest.mark.parametrize(
    "key",
    ["AGTHX", "EXS1.DE", "^GSPC", "..", "../../etc/passwd", "/etc/passwd", "a\\b", "x\x00y", ""],
)
def test_cache_files_stay_inside_the_cache_folder(tmp_path, monkeypatch, key):
    monkeypatch.setattr(data, "CACHE_DIR", tmp_path)
    path = data._cache_file("prices", key, ".csv")
    assert path.parent == tmp_path / "prices"
    assert path.name.endswith(".csv")
