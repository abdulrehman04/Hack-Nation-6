"""Read a PDF into tokens: word, box, confidence, and source (text layer or OCR).

Boxes use the gold convention: PDF points, bottom-left origin.
"""

from __future__ import annotations

import base64
from dataclasses import dataclass, asdict
from pathlib import Path

import fitz  # PyMuPDF
import pytesseract
from PIL import Image
from pytesseract import Output

# DPI to rasterize pages at before OCR.
OCR_DPI = 300

# Below this many words, treat the page as scanned and OCR it.
TEXT_LAYER_MIN_WORDS = 5


@dataclass
class Token:
    """One word and where it sits, in bottom-left-origin PDF points."""

    text: str
    bbox: tuple[float, float, float, float]
    confidence: float
    source: str  # "text_layer" | "ocr"
    page: int

    def as_dict(self) -> dict:
        return asdict(self)


@dataclass
class ExtractedDocument:
    """All tokens for a document plus how each page was read."""

    file_name: str
    page_size_points: tuple[float, float]
    method: str  # "text_layer" | "ocr" | "mixed"
    tokens: list[Token]
    watermark_terms: set[str]  # words found in rotated/watermark spans


# Coordinates

def _flip_y_to_bottom_left(x0: float, y0_top: float, x1: float, y1_top: float,
                           page_height: float) -> tuple[float, float, float, float]:
    """Flip a top-left-origin box to bottom-left origin (the gold convention)."""
    return (round(x0, 2), round(page_height - y1_top, 2),
            round(x1, 2), round(page_height - y0_top, 2))


# Per-page readers

def _extract_text_layer(page: "fitz.Page", page_no: int) -> list[Token]:
    """Read words straight from the PDF text layer. Digital text gets confidence 1."""
    height = page.rect.height
    tokens: list[Token] = []
    for x0, y0, x1, y1, word, *_ in page.get_text("words"):
        if not word.strip():
            continue
        tokens.append(Token(
            text=word,
            bbox=_flip_y_to_bottom_left(x0, y0, x1, y1, height),
            confidence=1.0,
            source="text_layer",
            page=page_no,
        ))
    return tokens


def _extract_ocr(page: "fitz.Page", page_no: int, dpi: int = OCR_DPI) -> list[Token]:
    """Render the page and OCR it. Pixel boxes are scaled back to points."""
    height = page.rect.height
    scale = 72.0 / dpi
    pix = page.get_pixmap(matrix=fitz.Matrix(dpi / 72, dpi / 72))
    image = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)

    data = pytesseract.image_to_data(image, output_type=Output.DICT)
    tokens: list[Token] = []
    for i, word in enumerate(data["text"]):
        if not word.strip():
            continue
        conf = float(data["conf"][i])
        if conf < 0:  # Tesseract uses -1 for non-text regions.
            continue
        left, top = data["left"][i] * scale, data["top"][i] * scale
        right = left + data["width"][i] * scale
        bottom = top + data["height"][i] * scale
        tokens.append(Token(
            text=word,
            bbox=_flip_y_to_bottom_left(left, top, right, bottom, height),
            confidence=round(conf / 100.0, 3),
            source="ocr",
            page=page_no,
        ))
    return tokens


# Reading a document

def page_is_digital(page: "fitz.Page") -> bool:
    """True if the page has a usable text layer, so we can skip OCR."""
    return len(page.get_text("words")) >= TEXT_LAYER_MIN_WORDS


def _rotated_span_terms(page: "fitz.Page") -> set[str]:
    """Words in rotated spans. The pack draws its watermark this way."""
    terms: set[str] = set()
    for block in page.get_text("dict")["blocks"]:
        if block.get("type") != 0:
            continue
        for line in block["lines"]:
            if abs(line["dir"][1]) <= 0.01:  # Horizontal text is real content.
                continue
            for span in line["spans"]:
                for word in span["text"].split():
                    if word.strip():
                        terms.add(word.strip().upper())
    return terms


def _read_open_doc(doc: "fitz.Document", file_name: str,
                   force_method: str | None) -> ExtractedDocument:
    """Read an already-open document into an ExtractedDocument."""
    tokens: list[Token] = []
    methods: set[str] = set()
    terms: set[str] = set()
    size = (doc[0].rect.width, doc[0].rect.height)
    for page_no, page in enumerate(doc, start=1):
        terms |= _rotated_span_terms(page)
        use_ocr = (force_method == "ocr") or (
            force_method != "text_layer" and not page_is_digital(page))
        if use_ocr:
            tokens.extend(_extract_ocr(page, page_no))
            methods.add("ocr")
        else:
            tokens.extend(_extract_text_layer(page, page_no))
            methods.add("text_layer")

    method = methods.pop() if len(methods) == 1 else "mixed"
    return ExtractedDocument(
        file_name=file_name,
        page_size_points=size,
        method=method,
        tokens=tokens,
        watermark_terms=terms,
    )


def extract_document(path: str | Path, force_method: str | None = None) -> ExtractedDocument:
    """Read a PDF from disk, picking text layer or OCR per page.

    Pass force_method="text_layer" or "ocr" to skip auto-detection.
    """
    path = Path(path)
    doc = fitz.open(path)
    try:
        return _read_open_doc(doc, path.name, force_method)
    finally:
        doc.close()


def extract_bytes(data: bytes, file_name: str, force_method: str | None = None) -> ExtractedDocument:
    """Read an uploaded PDF from memory, without touching disk."""
    doc = fitz.open(stream=data, filetype="pdf")
    try:
        return _read_open_doc(doc, file_name, force_method)
    finally:
        doc.close()


def render_first_page(data: bytes, dpi: int = 150) -> tuple[str, tuple[float, float]]:
    """Render page 1 to a base64 PNG data URL, with the page size in points."""
    doc = fitz.open(stream=data, filetype="pdf")
    try:
        page = doc[0]
        size = (page.rect.width, page.rect.height)
        pix = page.get_pixmap(matrix=fitz.Matrix(dpi / 72, dpi / 72))
        png = pix.tobytes("png")
    finally:
        doc.close()
    encoded = base64.b64encode(png).decode("ascii")
    return f"data:image/png;base64,{encoded}", size


# Box geometry, used to check tokens against gold boxes

def boxes_overlap(a: tuple[float, float, float, float],
                  b: tuple[float, float, float, float]) -> float:
    """Intersection-over-union of two boxes. Zero when they don't overlap."""
    ax0, ay0, ax1, ay1 = a
    bx0, by0, bx1, by1 = b
    ix0, iy0 = max(ax0, bx0), max(ay0, by0)
    ix1, iy1 = min(ax1, bx1), min(ay1, by1)
    if ix0 >= ix1 or iy0 >= iy1:
        return 0.0
    inter = (ix1 - ix0) * (iy1 - iy0)
    union = (ax1 - ax0) * (ay1 - ay0) + (bx1 - bx0) * (by1 - by0) - inter
    return inter / union if union else 0.0


def tokens_in_box(tokens: list[Token], box: tuple[float, float, float, float],
                  min_iou: float = 0.10) -> list[Token]:
    """Tokens whose box meaningfully overlaps a target region (e.g. a gold box)."""
    return [t for t in tokens if boxes_overlap(t.bbox, box) >= min_iou]
