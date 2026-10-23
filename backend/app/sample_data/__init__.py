"""Bundled demonstration material."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

DEMO_PDF = Path(__file__).with_name("nlp_fundamentals_demo.pdf")


@lru_cache(maxsize=1)
def demo_pdf_bytes() -> bytes:
    if DEMO_PDF.exists():
        return DEMO_PDF.read_bytes()
    # Fallback: render the synthetic notes on the fly if the bundled file is missing.
    from app.sample_data.demo_content import NOTICE, SECTIONS, TITLE
    from app.utils.sample_docs import build_pdf

    return build_pdf(TITLE, SECTIONS, NOTICE)
