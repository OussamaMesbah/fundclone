"""Pull identifiers out of a fund factsheet PDF to help find its Yahoo Finance ticker.

PDFs from users are untrusted: parse_factsheet_safely reads them in a separate process with
limits on pages, memory and processor time, so a malicious file cannot exhaust the web app.
"""

from __future__ import annotations

import io
import json
import re
import subprocess
import sys
from collections import Counter
from typing import BinaryIO

ISIN_RE = re.compile(r"\b[A-Z]{2}[A-Z0-9]{9}[0-9]\b")
LABELLED_TICKER_RE = re.compile(
    r"\b(?i:ticker|symbol|bloomberg(?: code| ticker)?)\s*[:\-]?\s*"
    r"([A-Z][A-Z0-9]{1,5}(?:[.\-][A-Z]{1,2})?)\b"
)
PARENTHESISED_TICKER_RE = re.compile(r"\(([A-Z]{3,5})\)")
MAX_PAGES = 5  # factsheets name the fund and its identifiers on the first pages
MEMORY_LIMIT_MB = 1024  # address space of the parsing process, where the system enforces it
CPU_SECONDS = 10


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


def parse_factsheet(pdf: str | BinaryIO, max_pages: int = MAX_PAGES) -> dict:
    """Parse the first `max_pages` pages of a factsheet given as a path or a binary file.

    Use parse_factsheet_safely for files from untrusted sources.
    """
    import pdfplumber  # optional dependency, installed with the "app" extra

    with pdfplumber.open(pdf) as document:
        text = "\n".join(page.extract_text() or "" for page in document.pages[:max_pages])
    return parse_factsheet_text(text)


def parse_factsheet_safely(pdf: bytes, timeout: float = 20.0) -> dict:
    """parse_factsheet on untrusted PDF bytes, in a separate Python process that may use at
    most MEMORY_LIMIT_MB of memory (where the system enforces the limit) and CPU_SECONDS of
    processor time. Raises ValueError when the PDF cannot be read within those limits."""
    # Runs this file alone, without importing the package or putting its folder on sys.path.
    child = "import runpy, sys; runpy.run_path(sys.argv[1], run_name='__main__')"
    try:
        result = subprocess.run(
            [sys.executable, "-c", child, __file__],
            input=pdf,
            capture_output=True,
            timeout=timeout,
            check=False,
        )
    except subprocess.TimeoutExpired:
        raise ValueError("Reading the PDF took too long.") from None
    if result.returncode != 0:
        raise ValueError("The PDF could not be read.")
    return json.loads(result.stdout)


def _limit_resources() -> None:
    try:
        import resource
    except ImportError:  # not available on Windows
        return
    memory = MEMORY_LIMIT_MB * 1024 * 1024
    for name, value in (("RLIMIT_AS", memory), ("RLIMIT_CPU", CPU_SECONDS)):
        try:
            resource.setrlimit(getattr(resource, name), (value, value))
        except (AttributeError, ValueError, OSError):  # macOS does not enforce every limit
            pass


if __name__ == "__main__":
    _limit_resources()
    json.dump(parse_factsheet(io.BytesIO(sys.stdin.buffer.read())), sys.stdout)
