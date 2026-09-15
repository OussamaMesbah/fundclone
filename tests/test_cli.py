import pytest
from fakes import analyse

import fundclone
from fundclone import cli


def test_version(capsys):
    with pytest.raises(SystemExit) as stop:
        cli.main(["--version"])
    assert stop.value.code == 0
    assert capsys.readouterr().out == f"fundclone {fundclone.__version__}\n"


def test_an_input_error_ends_with_a_message_not_a_traceback(monkeypatch, capsys):
    def fail(*args, **kwargs):
        raise ValueError("No price data for XXXX on Yahoo Finance.")

    monkeypatch.setattr(cli, "run_analysis", fail)
    with pytest.raises(SystemExit) as stop:
        cli.main(["XXXX"])
    assert stop.value.code == 1
    assert capsys.readouterr().err == "fundclone: No price data for XXXX on Yahoo Finance.\n"


@pytest.mark.parametrize(
    "args",
    [
        ["AGTHX", "--max-etfs", "0"],
        ["AGTHX", "--start", "2026-01-01", "--end", "2025-01-01"],
        ["AGTHX", "--start", "01/01/2020"],
        ["AGTHX", "--asset-classes", "stocks"],
        ["AGTHX", "--expense-ratio", "12"],
        ["AGTHX", "--expense-ratio", "abc"],
    ],
)
def test_invalid_arguments_are_rejected(args):
    with pytest.raises(SystemExit) as stop:
        cli.main(args)
    assert stop.value.code == 2


def test_asset_classes_are_matched_regardless_of_case(monkeypatch):
    seen = {}

    def capture(target, start, end, **kwargs):
        seen.update(kwargs)
        raise ValueError("stop")

    monkeypatch.setattr(cli, "run_analysis", capture)
    with pytest.raises(SystemExit):
        cli.main(["AGTHX", "--asset-classes", "bonds, us equity"])
    assert seen["asset_classes"] == ["Bonds", "US equity"]


def test_the_report_prints(monkeypatch, capsys):
    monkeypatch.setattr(cli, "run_analysis", lambda target, *args, **kwargs: analyse(target))
    cli.main(["FUND"])
    out = capsys.readouterr().out
    assert "A clone of" in out
    assert "Factor exposures" in out


def test_asset_classes_are_those_of_the_chosen_etf_set():
    import argparse

    from fundclone.cli import _asset_classes

    parser = argparse.ArgumentParser()
    assert _asset_classes(parser, "world equity, eur bonds", "UCITS") == [
        "World equity",
        "EUR bonds",
    ]
    with pytest.raises(SystemExit):
        _asset_classes(parser, "US equity", "UCITS")


def test_an_expense_ratio_is_given_in_percent(monkeypatch):
    seen = {}

    def capture(target, start, end, **kwargs):
        seen.update(kwargs)
        raise ValueError("stop")

    monkeypatch.setattr(cli, "run_analysis", capture)
    with pytest.raises(SystemExit):
        cli.main(["FUND", "--expense-ratio", "1.5"])
    assert seen["expense_ratio"] == pytest.approx(0.015)
