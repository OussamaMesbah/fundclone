"""Pull identifiers out of a fund factsheet PDF to help find its Yahoo Finance ticker."""

from __future__ import annotations

import re
from collections import Counter
from typing import BinaryIO

ISIN_RE = re.compile(r"\b[A-Z]{2}[A-Z0-9]{9}[0-9]\b")
LABELLED_TICKER_RE = re.compile(
    r"\b(?i:ticker|symbol|bloomberg(?: code| ticker)?)\s*[:\-]?\s*"
    r"([A-Z][A-Z0-9]{1,5}(?:[.\-][A-Z]{1,2})?)\b"
)
PARENTHESISED_TICKER_RE = re.compile(r"\(([A-Z]{3,5})\)")


def is_valid_isin(code: str) -> bool:
    """Check the format and the Luhn check digit of an ISIN."""
    if not ISIN_RE.fullmatch(code):
        return False
    digits = "".join(str(int(ch, 36)) for ch in code)
    total = 0
    for i, ch in enumerate(reversed(digits)):
        d = int(ch) * (2 if i % 2 else 1)
        total += d - 9 if d > 9 else d
    return total % 10 == 0


def parse_factsheet_text(text: str) -> dict:
    """Fund name guess, valid ISINs and ticker candidates found in a factsheet's text."""
    lines = [line.strip() for line in text.splitlines() if len(line.strip()) > 8]
    labelled = [t for t, _ in Counter(LABELLED_TICKER_RE.findall(text)).most_common()]
    parenthesised = [t for t, _ in Counter(PARENTHESISED_TICKER_RE.findall(text)).most_common()]
    return {
        "fund_name": lines[0][:120] if lines else "",
        "isins": sorted({code for code in ISIN_RE.findall(text) if is_valid_isin(code)}),
        "ticker_candidates": list(dict.fromkeys(labelled + parenthesised))[:5],
    }


def parse_factsheet(pdf: str | BinaryIO) -> dict:
    """Parse a factsheet given as a path or a binary file object."""
    import pdfplumber  # optional dependency, installed with the "app" extra

    with pdfplumber.open(pdf) as document:
        text = "\n".join(page.extract_text() or "" for page in document.pages)
    return parse_factsheet_text(text)
