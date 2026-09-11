"""The benchmark's download script, on synthetic data."""

from fakes import fake_factors, fake_prices

from benchmarks import download


def test_the_snapshot_folder_is_created(tmp_path, monkeypatch):
    # The repository ships no data/ folder, so a fresh checkout has none to write into.
    monkeypatch.setattr(download, "fetch_prices", fake_prices)
    monkeypatch.setattr(download, "load_french_factors", fake_factors)
    snapshot = tmp_path / "data" / "prices.parquet"
    download.main(["--out", str(tmp_path / "out"), "--snapshot", str(snapshot)])
    assert snapshot.exists()
    assert (tmp_path / "out" / "closes.parquet").exists()
