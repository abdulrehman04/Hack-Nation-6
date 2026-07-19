"""Stage 1: read synthetic documents into typed, cited fields.

Pipeline: readers -> filters -> assembly. The renter confirms or corrects the
result before anything downstream uses it. OCR is one reader here (readers.py);
the stage also reads digital text layers, filters watermark and injection text,
and assembles fields.
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
