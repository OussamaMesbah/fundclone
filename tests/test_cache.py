"""Cache paths come from user input (tickers in the web app's URL) and must stay in the cache,
which must not grow without limit."""

import os

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


def test_the_cache_keeps_only_the_most_recent_files(tmp_path, monkeypatch):
    monkeypatch.setattr(data, "CACHE_DIR", tmp_path)
    monkeypatch.setattr(data, "MAX_CACHE_FILES", 3)
    for i in range(5):
        path = data._cache_file("prices", f"T{i}", ".csv")
        data._write(path, "date,close\n")
        os.utime(path, (i, i))  # distinct write times, oldest first
    assert sorted(p.name for p in (tmp_path / "prices").iterdir()) == ["T2.csv", "T3.csv", "T4.csv"]


def test_pruning_leaves_files_being_written_alone(tmp_path, monkeypatch):
    monkeypatch.setattr(data, "CACHE_DIR", tmp_path)
    monkeypatch.setattr(data, "MAX_CACHE_FILES", 1)
    folder = tmp_path / "prices"
    folder.mkdir()
    in_progress = folder / "T9.csv.123.tmp"  # another writer's file, before os.replace
    in_progress.write_text("date,close\n")
    os.utime(in_progress, (0, 0))
    for i in range(2):
        data._write(data._cache_file("prices", f"T{i}", ".csv"), "date,close\n")
    assert in_progress.exists()
    assert len([p for p in folder.iterdir() if p.suffix == ".csv"]) == 1


def test_the_file_just_written_is_kept_whatever_its_time_stamp(tmp_path, monkeypatch):
    # A concurrent writer's file can carry a later time stamp than the one just written.
    monkeypatch.setattr(data, "CACHE_DIR", tmp_path)
    monkeypatch.setattr(data, "MAX_CACHE_FILES", 1)
    newer = data._cache_file("prices", "T0", ".csv")
    data._write(newer, "date,close\n")
    os.utime(newer, (4e9, 4e9))  # in 2096
    written = data._cache_file("prices", "T1", ".csv")
    data._write(written, "date,close\n")
    assert written.exists() and not newer.exists()


def test_pruning_copes_with_equal_time_stamps(tmp_path, monkeypatch):
    monkeypatch.setattr(data, "CACHE_DIR", tmp_path)
    monkeypatch.setattr(data, "MAX_CACHE_FILES", 2)
    for i in range(3):
        path = data._cache_file("prices", f"T{i}", ".csv")
        path.parent.mkdir(exist_ok=True)
        path.write_text("date,close\n")
        os.utime(path, (1, 1))
    written = data._cache_file("prices", "T3", ".csv")
    data._write(written, "date,close\n")
    assert sorted(p.name for p in (tmp_path / "prices").iterdir()) == ["T2.csv", "T3.csv"]
