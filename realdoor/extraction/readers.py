"""Extraction layer for RealDoor Phase 1 (Profile).

Turns a one-page synthetic PDF into a unified list of tokens, each carrying a
bounding box, a confidence, and its provenance (text layer vs OCR). Boxes are
emitted in the gold-file convention: PDF points, bottom-left origin.

This layer only reads and locates text. It never decides eligibility and never
interprets embedded instructions -- every token is inert data for a later step.
"""

from __future__ import annotations

from dataclasses import dataclass, asdict
from pathlib import Path

import fitz  # PyMuPDF
import pytesseract
from PIL import Image
from pytesseract import Output

# OCR render resolution; 300 DPI is the accuracy/speed sweet spot for Tesseract.
OCR_DPI = 300

# A page with fewer real words than this is treated as scanned and sent to OCR.
TEXT_LAYER_MIN_WORDS = 5


@dataclass
class Token:
    """One recognized word, located in bottom-left-origin PDF points."""

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


# --- coordinate helpers ---------------------------------------------------

def _flip_y_to_bottom_left(x0: float, y0_top: float, x1: float, y1_top: float,
                           page_height: float) -> tuple[float, float, float, float]:
    """Convert a top-left-origin box to the gold bottom-left-origin convention."""
    return (round(x0, 2), round(page_height - y1_top, 2),
            round(x1, 2), round(page_height - y0_top, 2))


# --- per-page extractors --------------------------------------------------

def _extract_text_layer(page: "fitz.Page", page_no: int) -> list[Token]:
    """Pull embedded words with exact boxes; digital text is treated as certain."""
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
    """Render the page and OCR it; pixel boxes are scaled to points and flipped."""
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
        if conf < 0:  # -1 marks non-text regions
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


# --- public API -----------------------------------------------------------

def page_is_digital(page: "fitz.Page") -> bool:
    """A real text layer means we can skip OCR for this page."""
    return len(page.get_text("words")) >= TEXT_LAYER_MIN_WORDS


def _rotated_span_terms(page: "fitz.Page") -> set[str]:
    """Words drawn in rotated spans; the pack renders its watermark this way."""
    terms: set[str] = set()
    for block in page.get_text("dict")["blocks"]:
        if block.get("type") != 0:
            continue
        for line in block["lines"]:
            if abs(line["dir"][1]) <= 0.01:  # horizontal text is content
                continue
            for span in line["spans"]:
                for word in span["text"].split():
                    if word.strip():
                        terms.add(word.strip().upper())
    return terms


def extract_document(path: str | Path, force_method: str | None = None) -> ExtractedDocument:
    """Extract every page, choosing text layer or OCR per page unless forced.

    force_method: "text_layer" or "ocr" to override auto-detection.
    """
    path = Path(path)
    doc = fitz.open(path)
    try:
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
    finally:
        doc.close()

    method = methods.pop() if len(methods) == 1 else "mixed"
    return ExtractedDocument(
        file_name=path.name,
        page_size_points=size,
        method=method,
        tokens=tokens,
        watermark_terms=terms,
    )


# --- box geometry (for validating against gold) ---------------------------

def boxes_overlap(a: tuple[float, float, float, float],
                  b: tuple[float, float, float, float]) -> float:
    """Intersection-over-union of two bottom-left-origin boxes; 0 when disjoint."""
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
