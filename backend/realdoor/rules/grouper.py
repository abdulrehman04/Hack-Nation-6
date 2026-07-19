"""Group Stage 01 extraction output by household.

Reads config.EXTRACTION_OUTPUT (a JSON array of document records, same shape
as data/gold/document_gold.jsonl). Quarantined fields — injected instructions
already caught and neutralized in Stage 01 — are dropped here and never reach
Stage 02 arithmetic or the Phase 2 chat context.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field

from .. import config


@dataclass
class Document:
    """One document's confirmed fields, keyed by field name. Quarantined fields excluded."""

    document_id: str
    household_id: str
    document_type: str
    file_name: str
    contains_adversarial_text: bool
    fields: dict[str, dict] = field(default_factory=dict)
    quarantined_count: int = 0

    def value(self, name: str):
        """The confirmed value for a field, or None if absent/quarantined/abstained."""
        entry = self.fields.get(name)
        return entry["value"] if entry else None

    def citation(self, name: str) -> dict | None:
        """Source citation (document_id, file_name, page, bbox) for a field's value."""
        entry = self.fields.get(name)
        if not entry:
            return None
        return {
            "document_id": self.document_id,
            "file_name": self.file_name,
            "page": entry["page"],
            "bbox": entry["bbox"],
        }


def load_documents(path=None) -> list[Document]:
    """Load extraction_output.json into Document records, dropping quarantined fields."""
    out_path = path or config.EXTRACTION_OUTPUT
    with out_path.open(encoding="utf-8") as f:
        records = json.load(f)

    documents = []
    for record in records:
        confirmed: dict[str, dict] = {}
        quarantined_count = 0
        for entry in record["fields"]:
            if entry["status"] == "quarantined":
                quarantined_count += 1
                continue
            if entry["status"] != "extracted":
                continue
            confirmed[entry["field"]] = entry
        documents.append(Document(
            document_id=record["document_id"],
            household_id=record["household_id"],
            document_type=record["document_type"],
            file_name=record["file_name"],
            contains_adversarial_text=record["contains_adversarial_text"],
            fields=confirmed,
            quarantined_count=quarantined_count,
        ))
    return documents


# Building pipeline documents from a saved, renter-confirmed profile (Firestore)

_INT_RE = re.compile(r"-?\d+")
_FLOAT_RE = re.compile(r"-?\d*\.\d+")


def _coerce(value):
    """Turn a UI-edited numeric string back into a number; leave dates and text alone."""
    if not isinstance(value, str):
        return value
    cleaned = value.strip().lstrip("$").replace(",", "")
    if _INT_RE.fullmatch(cleaned):
        return int(cleaned)
    if _FLOAT_RE.fullmatch(cleaned):
        return float(cleaned)
    return value


def documents_from_confirmed(household_id: str, stored_documents: list[dict]) -> list[Document]:
    """Build pipeline Documents from a saved profile's confirmed fields (the source of truth).

    Corrections live here, not in the frozen extraction file, so downstream math recomputes.
    Quarantined fields never reach a saved profile, so nothing needs dropping.
    """
    documents = []
    for index, stored in enumerate(stored_documents):
        document_type = stored.get("document_type") or "unknown"
        file_name = stored.get("file_name") or f"{household_id.lower()}-{document_type}-{index}"
        confirmed: dict[str, dict] = {}
        for entry in stored.get("fields", []):
            name = entry.get("name")
            value = entry.get("value")
            if name is None or value is None:
                continue
            confirmed[name] = {
                "field": name,
                "value": _coerce(value),
                "page": entry.get("page"),
                "bbox": entry.get("bbox"),
                "bbox_units": entry.get("bbox_units", "pdf_points_bottom_left_origin"),
                "confidence": entry.get("confidence", 1.0),
                "status": "extracted",
            }
        documents.append(Document(
            document_id=f"{household_id.lower()}-{document_type}-{index}",
            household_id=household_id,
            document_type=document_type,
            file_name=file_name,
            contains_adversarial_text=False,
            fields=confirmed,
        ))
    return documents


def group_by_household(documents: list[Document]) -> dict[str, list[Document]]:
    """Group documents by household_id, preserving input order within each group."""
    groups: dict[str, list[Document]] = {}
    for doc in documents:
        groups.setdefault(doc.household_id, []).append(doc)
    return groups


def load_households(path=None) -> dict[str, list[Document]]:
    """Load and group extraction output by household in one call."""
    return group_by_household(load_documents(path))
