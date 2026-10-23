"""Structure-preserving text extraction for PDF, DOCX and PPTX files.

Each extractor returns an ordered list of ``Block`` objects: headings and paragraphs with
the page / slide / section number they came from, so every downstream artefact can cite
its source.
"""

from __future__ import annotations

import io
import re
import zipfile
from collections import Counter
from dataclasses import dataclass, field

from app.nlp.text import is_heading_like, join_lines, normalize_text, word_count

SUPPORTED_TYPES = {"pdf", "docx", "pptx"}
UNIT_LABELS = {"pdf": "page", "docx": "section", "pptx": "slide"}

_BULLET_START = re.compile(r"^\s*[•▪●◦⁃∙·■\-–*]\s+")
_PAGE_NUMBER = re.compile(r"^(?:page\s*)?\d{1,4}(?:\s*(?:/|of)\s*\d{1,4})?$", re.I)


@dataclass
class Block:
    text: str
    kind: str  # "heading" | "paragraph"
    level: int  # 1..3 for headings, 0 for paragraphs
    location: int  # 1-based page, slide or section number


@dataclass
class ExtractionResult:
    file_type: str
    unit_label: str
    unit_count: int
    blocks: list[Block]
    warnings: list[str] = field(default_factory=list)

    @property
    def word_count(self) -> int:
        return sum(word_count(b.text) for b in self.blocks)


class ExtractionError(Exception):
    """A user-facing extraction failure with a stable machine-readable code."""

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


def detect_file_type(filename: str, data: bytes) -> str:
    """Determine the file type from the extension and verify it against the file signature."""
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if ext not in SUPPORTED_TYPES:
        raise ExtractionError("unsupported_type", "Unsupported file type. Upload a PDF, DOCX or PPTX file.")
    if ext == "pdf":
        if not data[:1024].lstrip().startswith(b"%PDF"):
            raise ExtractionError("corrupted", "This file has a .pdf extension but is not a valid PDF.")
    else:
        if not data.startswith(b"PK"):
            raise ExtractionError("corrupted", f"This file has a .{ext} extension but is not a valid Office document.")
        try:
            with zipfile.ZipFile(io.BytesIO(data)) as zf:
                names = set(zf.namelist())
        except zipfile.BadZipFile as exc:
            raise ExtractionError("corrupted", "The document archive is damaged and cannot be opened.") from exc
        marker = "word/document.xml" if ext == "docx" else "ppt/presentation.xml"
        if marker not in names:
            raise ExtractionError("corrupted", f"This file is not a valid .{ext} document.")
    return ext


def extract(filename: str, data: bytes, max_pages: int = 400) -> ExtractionResult:
    file_type = detect_file_type(filename, data)
    if file_type == "pdf":
        result = extract_pdf(data, max_pages)
    elif file_type == "docx":
        result = extract_docx(data)
    else:
        result = extract_pptx(data, max_pages)
    result.blocks = [b for b in result.blocks if b.text]
    if result.word_count < 40:
        raise ExtractionError(
            "insufficient_text",
            f"Only {result.word_count} words of readable text were found. StudyForge needs at least "
            "40 words of selectable text to build topics and questions.",
        )
    return result


# --------------------------------------------------------------------------- PDF


def extract_pdf(data: bytes, max_pages: int) -> ExtractionResult:
    import fitz  # PyMuPDF

    try:
        doc = fitz.open(stream=data, filetype="pdf")
    except Exception as exc:  # noqa: BLE001 - PyMuPDF raises several error types
        raise ExtractionError("corrupted", "The PDF is damaged or could not be parsed.") from exc
    with doc:
        if doc.needs_pass:
            raise ExtractionError("encrypted", "This PDF is password-protected. Remove the password and upload again.")
        if doc.page_count == 0:
            raise ExtractionError("empty", "The PDF has no pages.")
        if doc.page_count > max_pages:
            raise ExtractionError("too_large", f"The PDF has {doc.page_count} pages; the limit is {max_pages} pages.")

        raw_blocks: list[tuple[int, list[str], float, bool]] = []  # page, lines, max size, all bold
        size_weights: Counter[float] = Counter()
        image_only_pages = 0
        for page_index, page in enumerate(doc, start=1):
            page_dict = page.get_text("dict", flags=fitz.TEXT_PRESERVE_WHITESPACE | fitz.TEXT_MEDIABOX_CLIP)
            page_chars = 0
            for block in page_dict.get("blocks", []):
                if block.get("type") != 0:
                    continue
                lines: list[str] = []
                sizes: list[float] = []
                bold_flags: list[bool] = []
                for line in block.get("lines", []):
                    spans = [s for s in line.get("spans", []) if s.get("text", "").strip()]
                    if not spans:
                        continue
                    lines.append("".join(s["text"] for s in line["spans"]))
                    for span in spans:
                        size = round(float(span.get("size", 0)), 1)
                        n = len(span["text"].strip())
                        size_weights[size] += n
                        sizes.append(size)
                        bold_flags.append(bool(span.get("flags", 0) & 16) or "bold" in span.get("font", "").lower())
                        page_chars += n
                if lines:
                    raw_blocks.append((page_index, lines, max(sizes), all(bold_flags)))
            if page_chars < 20 and page.get_images(full=False):
                image_only_pages += 1

        total_chars = sum(size_weights.values())
        if total_chars < 200 and image_only_pages > 0:
            raise ExtractionError(
                "scanned_pdf",
                "This PDF appears to be scanned images without selectable text. StudyForge does not include "
                "OCR; export the document with selectable text (or run it through an OCR tool first).",
            )
        warnings: list[str] = []
        if image_only_pages and image_only_pages >= max(1, doc.page_count // 5):
            warnings.append(f"{image_only_pages} page(s) contain only images (likely scanned) and were skipped.")
        body_size = size_weights.most_common(1)[0][0] if size_weights else 10.0
        blocks = _pdf_blocks_to_blocks(raw_blocks, body_size, doc.page_count)
        return ExtractionResult("pdf", "page", doc.page_count, blocks, warnings)


def _pdf_blocks_to_blocks(
    raw_blocks: list[tuple[int, list[str], float, bool]], body_size: float, page_count: int
) -> list[Block]:
    # Detect repeated running headers/footers (same text on many pages) and drop them.
    def key(lines: list[str]) -> str:
        return re.sub(r"\d+", "#", " ".join(lines).strip().lower())

    page_keys: dict[str, set[int]] = {}
    for page, lines, _size, _bold in raw_blocks:
        page_keys.setdefault(key(lines), set()).add(page)
    # Only short blocks can be running headers or footers; repeated long passages are real content.
    repeated = {
        k
        for k, pages in page_keys.items()
        if page_count >= 3 and len(pages) >= max(3, page_count * 0.5) and len(k.split()) <= 15
    }

    heading_sizes = sorted({size for _p, lines, size, _b in raw_blocks if size >= body_size * 1.15}, reverse=True)
    level_for_size = {size: min(i + 1, 3) for i, size in enumerate(heading_sizes)}

    blocks: list[Block] = []
    for page, lines, size, bold in raw_blocks:
        if key(lines) in repeated:
            continue
        text = normalize_text(join_lines(lines))
        if not text or _PAGE_NUMBER.match(text):
            continue
        if size in level_for_size and is_heading_like(text):
            blocks.append(Block(text, "heading", level_for_size[size], page))
            continue
        if bold and len(lines) <= 2 and is_heading_like(text) and word_count(text) >= 1:
            blocks.append(Block(text, "heading", 3, page))
            continue
        # Split blocks that contain bullet lists into separate paragraphs.
        if sum(1 for line in lines if _BULLET_START.match(line)) >= 2:
            current: list[str] = []
            for line in lines:
                if _BULLET_START.match(line) and current:
                    blocks.append(Block(normalize_text(join_lines(current)), "paragraph", 0, page))
                    current = []
                current.append(line)
            if current:
                blocks.append(Block(normalize_text(join_lines(current)), "paragraph", 0, page))
        else:
            blocks.append(Block(text, "paragraph", 0, page))
    return _merge_broken_paragraphs(blocks)


def _merge_broken_paragraphs(blocks: list[Block]) -> list[Block]:
    """Re-join paragraphs split across a page or column break mid-sentence."""
    merged: list[Block] = []
    for block in blocks:
        prev = merged[-1] if merged else None
        if (
            prev is not None
            and block.kind == "paragraph"
            and prev.kind == "paragraph"
            and block.location == prev.location + 1
            and not prev.text.endswith((".", "?", "!", ":", ";"))
            and block.text[:1].islower()
        ):
            prev.text = join_lines([prev.text, block.text])
            continue
        merged.append(block)
    return merged


# --------------------------------------------------------------------------- DOCX


def extract_docx(data: bytes) -> ExtractionResult:
    import docx
    from docx.table import Table
    from docx.text.paragraph import Paragraph

    try:
        document = docx.Document(io.BytesIO(data))
    except Exception as exc:  # noqa: BLE001
        raise ExtractionError("corrupted", "The Word document is damaged or could not be parsed.") from exc

    blocks: list[Block] = []
    section = 1
    seen_heading = False
    body = document.element.body
    for child in body.iterchildren():
        tag = child.tag.rsplit("}", 1)[-1]
        if tag == "p":
            para = Paragraph(child, document)
            text = normalize_text(para.text)
            if not text:
                continue
            style = (para.style.name if para.style is not None else "") or ""
            level = _docx_heading_level(style, para, text)
            if level:
                if seen_heading or blocks:
                    section += 1
                seen_heading = True
                blocks.append(Block(text, "heading", level, section))
            else:
                blocks.append(Block(text, "paragraph", 0, section))
        elif tag == "tbl":
            table = Table(child, document)
            for row in table.rows:
                cells: list[str] = []
                for cell in row.cells:
                    value = normalize_text(cell.text)
                    if value and (not cells or cells[-1] != value):
                        cells.append(value)
                if cells:
                    joined = " — ".join(cells) if len(cells) == 2 else "; ".join(cells)
                    blocks.append(Block(joined, "paragraph", 0, section))
    return ExtractionResult("docx", "section", section, blocks)


def _docx_heading_level(style: str, para, text: str) -> int:
    name = style.lower()
    if name == "title":
        return 1
    match = re.match(r"heading\s*(\d)", name)
    if match:
        return min(int(match.group(1)), 3)
    runs = [r for r in para.runs if r.text.strip()]
    if runs and all(r.bold for r in runs) and is_heading_like(text) and word_count(text) <= 8:
        return 3
    return 0


# --------------------------------------------------------------------------- PPTX


def extract_pptx(data: bytes, max_slides: int) -> ExtractionResult:
    from pptx import Presentation

    try:
        prs = Presentation(io.BytesIO(data))
    except Exception as exc:  # noqa: BLE001
        raise ExtractionError("corrupted", "The PowerPoint file is damaged or could not be parsed.") from exc

    slides = list(prs.slides)
    if not slides:
        raise ExtractionError("empty", "The presentation has no slides.")
    if len(slides) > max_slides:
        raise ExtractionError("too_large", f"The presentation has {len(slides)} slides; the limit is {max_slides}.")

    blocks: list[Block] = []
    for number, slide in enumerate(slides, start=1):
        title_shape = slide.shapes.title
        title = (
            normalize_text(title_shape.text_frame.text)
            if title_shape is not None and title_shape.has_text_frame
            else ""
        )
        if title:
            blocks.append(Block(title, "heading", 1, number))
        shapes = [s for s in slide.shapes if title_shape is None or s.shape_id != title_shape.shape_id]
        shapes.sort(key=lambda s: ((s.top or 0), (s.left or 0)))
        for shape in shapes:
            blocks.extend(_pptx_shape_blocks(shape, number))
        if slide.has_notes_slide:
            notes = slide.notes_slide.notes_text_frame
            if notes is not None:
                for para in notes.text.split("\n"):
                    text = normalize_text(para)
                    if word_count(text) >= 4:
                        blocks.append(Block(text, "paragraph", 0, number))
    return ExtractionResult("pptx", "slide", len(slides), blocks)


def _pptx_shape_blocks(shape, number: int) -> list[Block]:
    out: list[Block] = []
    if shape.shape_type == 6 and hasattr(shape, "shapes"):  # group shape
        for sub in shape.shapes:
            out.extend(_pptx_shape_blocks(sub, number))
        return out
    if getattr(shape, "has_table", False) and shape.has_table:
        for row in shape.table.rows:
            cells = [normalize_text(c.text) for c in row.cells if normalize_text(c.text)]
            if cells:
                out.append(Block(" — ".join(cells) if len(cells) == 2 else "; ".join(cells), "paragraph", 0, number))
        return out
    if getattr(shape, "has_text_frame", False) and shape.has_text_frame:
        for para in shape.text_frame.paragraphs:
            text = normalize_text("".join(run.text for run in para.runs) or "")
            if text:
                out.append(Block(text, "paragraph", 0, number))
    return out
