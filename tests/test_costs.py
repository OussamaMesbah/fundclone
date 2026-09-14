"""Sales loads and the cost of switching."""

import math

import pytest

from fundclone.costs import load_drag, sales_charge_hint, switching


@pytest.mark.parametrize(
    "name",
    [
        "American Funds Growth Fd of Amer A",
        "Some Equity Fund Class A",
        "Some Equity Fund Cl A",
        "Some Equity Fund A Shares",
    ],
)
def test_class_a_names_warn_about_a_front_end_load(name):
    assert "front-end sales load" in sales_charge_hint(name)


def test_other_share_classes():
    assert "deferred sales load" in sales_charge_hint("Some Fund Class C")
    assert "up to 2.5%" in sales_charge_hint("Some Fund Class T")


@pytest.mark.parametrize(
    "name",
    [
        "Vanguard Wellington Inv",
        "Fidelity Contrafund",
        "American Funds Growth Fd of Amer R-6",
        "Vanguard 500 Index Admiral",
        "",
        None,
    ],
)
def test_names_without_a_sales_class_warn_about_nothing(name):
    assert sales_charge_hint(name) is None


def test_a_load_becomes_an_annual_drag_over_the_holding_period():
    assert load_drag(0.0575, 10) == pytest.approx(0.0059, abs=0.0001)
    assert load_drag(0.0575, 1) == pytest.approx(0.0575)
    assert load_drag(0.0, 10) == 0.0
    assert load_drag(0.05, 0) == 0.0


def test_switching_costs_tax_now_and_pays_it_back_from_the_yearly_saving():
    result = switching(10_000, 0.4, 0.15, 0.005)
    assert result["tax"] == pytest.approx(600)
    assert result["yearly_saving"] == pytest.approx(50)
    assert result["years_to_recover"] == pytest.approx(12)


def test_switching_without_a_saving_never_pays_off_and_without_gains_costs_nothing():
    assert math.isinf(switching(10_000, 0.4, 0.15, 0.0)["years_to_recover"])
    assert switching(10_000, 0.0, 0.15, 0.005)["tax"] == 0.0
