"""Costs a fund's price history does not show: sales loads, and the tax of switching.

A fund's returns here come from its net asset value, which is after its expense ratio but
before any sales load, and no figure in FundClone knows what an investor owes in tax.
"""

from __future__ import annotations

import re

# A share class at the end of a fund's name, as Yahoo Finance writes it: "... Amer A",
# "... Class A", "... Cl C", "... A Shares".
_SHARE_CLASS = re.compile(r"(?:\bclass\s+|\bcl\s+|\s)([ACT])(?:\s+shares?)?$", re.IGNORECASE)
_CHARGES = {
    "A": (
        "Class A shares usually charge a front-end sales load, often up to 5.75% for stock "
        "funds. It is not in these returns, which follow the fund's net asset value, and "
        "other share classes of the same fund often charge less."
    ),
    "C": (
        "Class C shares usually charge a deferred sales load if sold in the first year, on "
        "top of a higher expense ratio. The load is not in these returns, which follow the "
        "fund's net asset value."
    ),
    "T": (
        "Class T shares usually charge a front-end sales load of up to 2.5%. It is not in "
        "these returns, which follow the fund's net asset value."
    ),
}


def sales_charge_hint(name: str | None) -> str | None:
    """A warning for share classes whose name says they charge a sales load, or None.

    The name is all there is to go by: Yahoo Finance reports expense ratios but no loads.
    """
    match = _SHARE_CLASS.search((name or "").strip())
    return _CHARGES.get(match.group(1).upper()) if match else None


def load_drag(load: float, years: float) -> float:
    """The annual return a one-off sales load costs over `years`.

    Paying 5.75% on the way in leaves 94.25% invested, which over ten years is the same as
    giving up 0.59% a year.
    """
    if load <= 0 or years <= 0:
        return 0.0
    return 1 - (1 - load) ** (1 / years)


def switching(amount: float, unrealised_gain: float, tax_rate: float, saved: float) -> dict:
    """Tax on selling a fund and how long a yearly saving takes to earn it back.

    `unrealised_gain` is the share of `amount` that is gains, `tax_rate` the rate on them
    and `saved` the yearly saving as a share of `amount`, such as the difference in fees.
    The tax is mostly paid earlier rather than extra, since selling later would owe it too;
    in a tax-deferred account there is none.
    """
    tax = amount * max(unrealised_gain, 0.0) * max(tax_rate, 0.0)
    yearly = amount * saved
    return {
        "tax": tax,
        "yearly_saving": yearly,
        "years_to_recover": tax / yearly if yearly > 0 else float("inf"),
    }
