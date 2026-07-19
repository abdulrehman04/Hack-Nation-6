"""Detect a document's type from its text.

Each type is recognized by its printed title and a couple of distinctive
labels. The type with the most signature hits wins; none means unrecognized.
"""

from __future__ import annotations

from .readers import ExtractedDocument

# Checked in order; ties keep the earlier entry.
_SIGNATURES: list[tuple[str, list[str]]] = [
    ("gig_statement", ["gig statement", "gross receipts", "platform fees"]),
    ("benefit_letter", ["benefit letter", "monthly amount", "recipient"]),
    ("employment_letter", ["employment letter", "hours per week", "letter date"]),
    ("pay_stub", ["pay stub", "gross pay", "net pay"]),
    ("application_summary", ["application summary", "mailing address", "household size"]),
]


def detect_document_type(extracted: ExtractedDocument) -> str | None:
    """Best-matching document type, or None if nothing matches."""
    text = " ".join(t.text for t in extracted.tokens).lower()
    best_type: str | None = None
    best_hits = 0
    for doc_type, phrases in _SIGNATURES:
        hits = sum(1 for phrase in phrases if phrase in text)
        if hits > best_hits:
            best_hits, best_type = hits, doc_type
    return best_type if best_hits else None
