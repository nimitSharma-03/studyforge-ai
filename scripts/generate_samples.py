"""Regenerate the synthetic demo documents (PDF, DOCX, PPTX).

Usage (from the repository root):
    backend/.venv/Scripts/python scripts/generate_samples.py   # Windows
    backend/.venv/bin/python scripts/generate_samples.py       # macOS / Linux
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend"))

from app.sample_data import DEMO_PDF  # noqa: E402
from app.sample_data.demo_content import NOTICE, SECTIONS, TITLE  # noqa: E402
from app.utils.sample_docs import build_docx, build_pdf, build_pptx  # noqa: E402


def main() -> None:
    out_dir = ROOT / "samples"
    out_dir.mkdir(exist_ok=True)
    pdf = build_pdf(TITLE, SECTIONS, NOTICE)
    outputs = {
        out_dir / "nlp_fundamentals_demo.pdf": pdf,
        out_dir / "nlp_fundamentals_demo.docx": build_docx(TITLE, SECTIONS, NOTICE),
        out_dir / "nlp_fundamentals_demo.pptx": build_pptx(TITLE, SECTIONS, NOTICE),
        DEMO_PDF: pdf,
    }
    for path, data in outputs.items():
        path.write_bytes(data)
        print(f"wrote {path.relative_to(ROOT)} ({len(data) // 1024} KB)")


if __name__ == "__main__":
    main()
