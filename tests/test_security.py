"""Limits on untrusted input: tickers, portfolios and factsheet PDFs."""

import io

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


def test_a_weight_too_large_to_be_a_number_is_rejected():
    with pytest.raises(ValueError, match="ordinary numbers"):
        parse_portfolio("VTI " + "9" * 400)


def tiny_pdf(*pages: str) -> bytes:
    """A PDF with one line of text per page, written by hand."""
    kids = " ".join(f"{4 + 2 * i} 0 R" for i in range(len(pages)))
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        f"<< /Type /Pages /Kids [{kids}] /Count {len(pages)} >>".encode(),
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    for i, text in enumerate(pages):
        stream = f"BT /F1 12 Tf 72 720 Td ({text}) Tj ET".encode()
        objects.append(
            f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents {5 + 2 * i} 0 R"
            " /Resources << /Font << /F1 3 0 R >> >> >>".encode()
        )
        objects.append(b"<< /Length %d >>\nstream\n" % len(stream) + stream + b"\nendstream")
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
    pytest.importorskip("pdfminer")
    info = factsheet.parse_factsheet_safely(tiny_pdf("Example Growth Fund Ticker: EXGRX"))
    assert info["ticker_candidates"] == ["EXGRX"]


def test_an_unreadable_pdf_raises_a_plain_error():
    with pytest.raises(ValueError, match="could not be read"):
        factsheet.parse_factsheet_safely(b"not a pdf")


def test_only_the_first_pages_of_a_factsheet_are_opened(monkeypatch):
    pytest.importorskip("pdfminer")
    from pdfminer.pdfpage import PDFPage

    create_pages = PDFPage.create_pages
    taken = []

    def counting(cls, document):
        for page in create_pages(document):
            taken.append(page)
            yield page

    monkeypatch.setattr(PDFPage, "create_pages", classmethod(counting))
    pages = ["Example Growth Fund factsheet"] * factsheet.MAX_PAGES + ["Ticker: LATER"]
    pdf = tiny_pdf(*pages)
    assert factsheet.parse_factsheet(io.BytesIO(pdf))["ticker_candidates"] == []
    assert len(taken) == factsheet.MAX_PAGES  # the last page is never even set up
    everything = factsheet.parse_factsheet(io.BytesIO(pdf), max_pages=len(pages))
    assert everything["ticker_candidates"] == ["LATER"]


@pytest.mark.parametrize("max_pages", [0, -1])
def test_a_page_limit_below_one_is_rejected(max_pages):
    # pdfminer would read every page for maxpages=0
    with pytest.raises(ValueError, match="at least 1"):
        factsheet.parse_factsheet(io.BytesIO(tiny_pdf("Example Growth Fund")), max_pages)
