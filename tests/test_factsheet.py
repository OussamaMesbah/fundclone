from factorlens.factsheet import is_valid_isin, parse_factsheet_text

FACTSHEET = """Example Balanced Fund - Institutional Class
Share class I (EXBFX)
Ticker: EXBAX
ISIN: US0378331005, and a typo: US0378331006
A balanced multi-asset allocation fund investing in bonds and equities.
"""


def test_isin_check_digit():
    assert is_valid_isin("US0378331005")
    assert not is_valid_isin("US0378331006")
    assert not is_valid_isin("not an isin")


def test_parse_factsheet_text():
    info = parse_factsheet_text(FACTSHEET)
    assert info["fund_name"] == "Example Balanced Fund - Institutional Class"
    assert info["isins"] == ["US0378331005"]
    assert info["ticker_candidates"] == ["EXBAX", "EXBFX"]
