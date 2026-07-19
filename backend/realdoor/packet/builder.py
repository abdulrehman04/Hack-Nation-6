"""Stage 03: assemble the exportable packet, and delete session data.

Never auto-sends the packet anywhere — the renter downloads it manually.
Session deletion never rewrites data/ or the shared out/extraction_output.json
(other households' demo data lives there too); instead it records a tombstone
that every Stage 02/03 endpoint checks before serving that household's data,
so deletion is real and observable without destroying shared demo state.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from .. import config

PACKET_VERSION = "1.0"

DISCLAIMER = (
    "RealDoor never approves, denies, scores, ranks, or determines "
    "eligibility. It compares a confirmed, cited figure against a frozen "
    "published threshold. Final determinations remain human and "
    "program-specific (rule CH-DECISION-001). Document contents are "
    "treated as untrusted data; embedded instructions are ignored."
)

ITEMS_DELETED = ["extraction_data", "enriched_profile", "chat_history"]


class DeletedSessionStore:
    """Tiny file-backed tombstone of which household_ids have been deleted."""

    def __init__(self, root):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self.path = self.root / "deleted_sessions.json"

    def _load(self) -> dict:
        if not self.path.exists():
            return {}
        return json.loads(self.path.read_text(encoding="utf-8"))

    def _save(self, data: dict) -> None:
        self.path.write_text(json.dumps(data, indent=2), encoding="utf-8")

    def mark_deleted(self, household_id: str, deleted_at: str) -> None:
        data = self._load()
        data[household_id] = deleted_at
        self._save(data)

    def is_deleted(self, household_id: str) -> bool:
        return household_id in self._load()


_session_store: DeletedSessionStore | None = None


def get_session_store() -> DeletedSessionStore:
    """Return the configured session-deletion tombstone store."""
    global _session_store
    if _session_store is None:
        _session_store = DeletedSessionStore(config.SESSION_STORE_DIR)
    return _session_store


def is_session_deleted(household_id: str) -> bool:
    """True if this household's session has been deleted."""
    return get_session_store().is_deleted(household_id)


def build_packet(household_id: str, enriched_profile: dict, checklist: list) -> dict:
    """Assemble the full exportable packet. Never auto-sends anywhere."""
    return {
        "packet_version": PACKET_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "disclaimer": DISCLAIMER,
        "household": {
            "household_id": enriched_profile["household_id"],
            "person_name": enriched_profile["person_name"],
            "household_size": enriched_profile["household_size"],
            "address": enriched_profile["address"],
            "application_date": enriched_profile["application_date"],
        },
        "income_calculation": {
            "annualized_income": enriched_profile["annualized_income"],
            "frozen_60_percent_threshold": enriched_profile["frozen_60_percent_threshold"],
            "comparison": enriched_profile["comparison"],
            "threshold_pct_used": enriched_profile["threshold_pct_used"],
            "readiness_status": enriched_profile["readiness_status"],
            "review_reasons": enriched_profile["review_reasons"],
            "income_sources": enriched_profile["income_sources"],
            "calculation_steps": enriched_profile["calculation_steps"],
            "rule_versions_used": enriched_profile["rule_versions_used"],
            "disclosure": enriched_profile["disclosure"],
        },
        "document_checklist": checklist,
        "citations": enriched_profile["citations"],
        "submission_schema_output": {
            "household_id": enriched_profile["household_id"],
            "annualized_income": enriched_profile["annualized_income"],
            "comparison": enriched_profile["comparison"],
            "readiness_status": enriched_profile["readiness_status"],
            "citations": enriched_profile["citations"],
        },
    }


def delete_session(household_id: str) -> dict:
    """Delete all session data for this household.

    Marks the household as deleted in the tombstone store (checked by every
    Stage 02/03 endpoint before serving data), rather than rewriting
    out/extraction_output.json or any other shared file. Never deletes the
    frozen rule corpus, MTSP data, gold checklists, or any other household's
    data — those are never keyed by household_id in a way this function
    touches.
    """
    deleted_at = datetime.now(timezone.utc).isoformat()
    get_session_store().mark_deleted(household_id, deleted_at)
    return {
        "deleted": True,
        "household_id": household_id,
        "deleted_at": deleted_at,
        "items_deleted": list(ITEMS_DELETED),
    }
