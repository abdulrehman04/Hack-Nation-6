"""Stage 1 — extract synthetic documents into typed, cited fields.

The renter confirms or corrects the result before it is reused downstream.
Pipeline: readers -> filters -> assembly.

    PDF -> readers   (text-layer or OCR tokens, boxes + confidence)
        -> filters   (drop watermark, quarantine injected instructions)
        -> assembly  (label-anchored typed fields, abstains when unsure)

OCR is only one reader here (see readers.py); this stage also reads digital
text layers, filters watermark/injection text, and assembles fields.
"""

from .assembly import AssembledDocument, Field, assemble
from .readers import ExtractedDocument, Token, extract_document

__all__ = [
    "Token",
    "ExtractedDocument",
    "extract_document",
    "Field",
    "AssembledDocument",
    "assemble",
]
