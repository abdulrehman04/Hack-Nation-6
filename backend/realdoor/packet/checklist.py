"""Stage 03: build a per-household document checklist.

Compares what the renter actually has (grouper.Document records — quarantined
fields already filtered out in Stage 01/02) against the gold checklist's
required document types for that household. Reports presence, count, and
currency per document type; never decides eligibility.
"""

from __future__ import annotations

import json

from .. import config
from ..rules import calculate
from ..rules.grouper import Document

MASTER_DOCUMENT_TYPES = [
    "application_summary",
    "pay_stub",
    "employment_letter",
    "benefit_letter",
    "gig_statement",
]

LABELS = {
    "application_summary": "Application summary",
    "pay_stub": "Pay stub(s)",
    "employment_letter": "Employment verification letter",
    "benefit_letter": "Benefit award letter",
    "gig_statement": "Gig / self-employment statement",
}

# Field checked for the 60-day currency window, per document type. Types
# absent here (application_summary, gig_statement) have no comparable date
# field in this system and are treated as current whenever present.
CURRENCY_FIELD = {
    "pay_stub": "pay_date",
    "employment_letter": "document_date",
    "benefit_letter": "document_date",
}

MESSAGES = {
    "PRESENT_AND_CURRENT": "{count} document(s) on file, current and consistent.",
    "PRESENT_BUT_EXPIRED": "{count} document(s) on file but expired (outside 60-day window).",
    "MISSING_REQUIRED": "Required — not found in submitted documents.",
    "NOT_PROVIDED_OPTIONAL": "Not provided (optional / only if applicable).",
}


def _label_for(document_type: str) -> str:
    return LABELS.get(document_type, document_type.replace("_", " ").capitalize())


def load_required_document_types(household_id: str, path=None) -> list[str]:
    """Required document types for a household, from the gold checklist file."""
    checklists_path = path or config.CHECKLISTS
    with checklists_path.open(encoding="utf-8") as f:
        records = json.load(f)
    for record in records:
        if record["household_id"] == household_id:
            return record["required_document_types"]
    raise KeyError(f"Unknown household_id in checklists: {household_id}")


def _employment_letter_substituted(documents: list[Document]) -> bool:
    """True when other current income evidence makes a missing employment_letter non-blocking.

    Mirrors pipeline.py's MISSING_REQUIRED_EVIDENCE rule: a current pay_stub or
    benefit_letter substitutes for employment_letter as income evidence.
    """
    has_current_pay_stub = any(
        calculate.is_current(d.value("pay_date")) for d in documents if d.document_type == "pay_stub"
    )
    has_current_benefit = any(
        calculate.is_current(d.value("document_date")) for d in documents if d.document_type == "benefit_letter"
    )
    return has_current_pay_stub or has_current_benefit


def _status_and_count(document_type: str, documents: list[Document], required: bool) -> tuple[str, int]:
    matches = [d for d in documents if d.document_type == document_type]
    count = len(matches)
    if count == 0:
        if document_type == "employment_letter" and _employment_letter_substituted(documents):
            return "NOT_PROVIDED_OPTIONAL", count
        return ("MISSING_REQUIRED" if required else "NOT_PROVIDED_OPTIONAL"), count

    date_field = CURRENCY_FIELD.get(document_type)
    if date_field is None:
        return "PRESENT_AND_CURRENT", count
    all_current = all(calculate.is_current(d.value(date_field)) for d in matches)
    return ("PRESENT_AND_CURRENT" if all_current else "PRESENT_BUT_EXPIRED"), count


def build_checklist(household_id: str, documents: list[Document], path=None) -> dict:
    """Build the document checklist for one household."""
    required = set(load_required_document_types(household_id, path))

    document_types = list(MASTER_DOCUMENT_TYPES)
    for extra in required:
        if extra not in document_types:
            document_types.append(extra)

    rows = []
    for document_type in document_types:
        is_required = document_type in required
        status, count = _status_and_count(document_type, documents, is_required)
        rows.append({
            "document_type": document_type,
            "label": _label_for(document_type),
            "optional": not is_required,
            "status": status,
            "count": count,
            "message": MESSAGES[status].format(count=count),
        })

    return {"household_id": household_id, "checklist": rows}
