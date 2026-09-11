"""Limits on untrusted input: tickers, portfolios and factsheet PDFs."""

import pytest

from fundclone import factsheet
from fundclone.portfolio import MAX_HOLDINGS, is_ticker, parse_portfolio


@pytest.mark.parametrize("text", ["AGTHX", "EXS1.DE", "BRK-B", "^GSPC", "EURUSD=X", "7203.T"])
def test_real_tickers_pass(text):
    assert is_ticker(text)


@pytest.mark.parametrize(
    "text", ["", "[Sign in](https://evil.example)", "A" * 21, "60", "VTI 60", "<script>"]
)
def test_other_text_is_not_a_ticker(text):
    assert not is_ticker(text)


def test_portfolios_have_a_limited_number_of_holdings():
    many = ", ".join(f"T{i:03d}X 1" for i in range(MAX_HOLDINGS + 1))
    with pytest.raises(ValueError, match="at most"):
        parse_portfolio(many)
    assert len(parse_portfolio(", ".join(f"T{i:03d}X 1" for i in range(MAX_HOLDINGS)))) == 30


def tiny_pdf(text: str) -> bytes:
    """A one-page PDF with a line of text, written by hand."""
    stream = f"BT /F1 12 Tf 72 720 Td ({text}) Tj ET".encode()
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R"
        b" /Resources << /Font << /F1 5 0 R >> >> >>",
        b"<< /Length %d >>\nstream\n" % len(stream) + stream + b"\nendstream",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    out = bytearray(b"%PDF-1.4\n")
    offsets = []
    for number, body in enumerate(objects, 1):
        offsets.append(len(out))
        out += b"%d 0 obj\n" % number + body + b"\nendobj\n"
    xref = len(out)
    out += b"xref\n0 %d\n0000000000 65535 f \n" % (len(objects) + 1)
    out += b"".join(b"%010d 00000 n \n" % offset for offset in offsets)
    out += b"trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF\n" % (
        len(objects) + 1,
        xref,
    )
    return bytes(out)


def test_factsheets_are_read_in_a_separate_process():
    pytest.importorskip("pdfplumber")
    info = factsheet.parse_factsheet_safely(tiny_pdf("Example Growth Fund Ticker: EXGRX"))
    assert info["ticker_candidates"] == ["EXGRX"]


def test_an_unreadable_pdf_raises_a_plain_error():
    with pytest.raises(ValueError, match="could not be read"):
        factsheet.parse_factsheet_safely(b"not a pdf")
