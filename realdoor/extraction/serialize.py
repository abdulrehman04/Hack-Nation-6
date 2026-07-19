"""Serialize an assembled document into the gold record schema.

Same keys as data/gold/document_gold.jsonl, so output diffs cleanly against the
gold. Our extra keys (confidence, status) come after the gold ones.
"""

from __future__ import annotations

from .assembly import AssembledDocument
from .readers import ExtractedDocument

BBOX_UNITS = "pdf_points_bottom_left_origin"

# Keys every gold record and field carry. Our output must include all of them.
GOLD_TOP_KEYS = [
    "document_id", "household_id", "document_type", "file_name",
    "synthetic", "rasterized", "contains_adversarial_text",
    "page_count", "page_size_points", "fields",
]
GOLD_FIELD_KEYS = ["field", "value", "page", "bbox", "bbox_units"]


def _dim(value: float):
    """Emit whole numbers as ints (matching the gold's [612, 792])."""
    return int(value) if float(value).is_integer() else round(value, 2)


def to_gold_record(document_id: str, household_id: str, file_name: str,
                   extracted: ExtractedDocument, assembled: AssembledDocument) -> dict:
    """Map our extraction result onto the gold document-record schema."""
    width, height = extracted.page_size_points
    page_count = max((t.page for t in extracted.tokens), default=1)

    fields = []
    for f in assembled.fields:
        fields.append({
            "field": f.name,
            "value": f.value,
            "page": 1,
            "bbox": [round(v, 2) for v in f.source_bbox] if f.source_bbox else None,
            "bbox_units": BBOX_UNITS,
            "confidence": f.confidence,
            "status": f.status,
        })

    return {
        "document_id": document_id,
        "household_id": household_id,
        "document_type": assembled.document_type,
        "file_name": file_name,
        "synthetic": True,
        "rasterized": assembled.method == "ocr",
        "contains_adversarial_text": assembled.injected_instruction is not None,
        "page_count": page_count,
        "page_size_points": [_dim(width), _dim(height)],
        "fields": fields,
    }
