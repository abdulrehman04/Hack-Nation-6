"""File-backed ProfileStore: one JSON file per profile, plus an index.

Stands in for a database. Each record gets an id, a created timestamp, and a
status, the way a row would. Swapping to a real database means writing another
ProfileStore and changing the factory in __init__.py.
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path

from .base import ProfileStore, household_id_from_documents


class JsonProfileStore(ProfileStore):
    def __init__(self, root: str | Path):
        self.root = Path(root)
        self.profiles_dir = self.root / "profiles"
        self.index_path = self.root / "index.json"
        self.profiles_dir.mkdir(parents=True, exist_ok=True)

    def save(self, profile: dict) -> str:
        profile_id = profile.get("profile_id") or uuid.uuid4().hex[:12]
        record = {
            "profile_id": profile_id,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "status": "confirmed",
            **profile,
        }
        path = self.profiles_dir / f"{profile_id}.json"
        path.write_text(json.dumps(record, indent=2), encoding="utf-8")
        self._index_upsert(record)
        return profile_id

    def get(self, profile_id: str) -> dict | None:
        path = self.profiles_dir / f"{profile_id}.json"
        if not path.exists():
            return None
        return json.loads(path.read_text(encoding="utf-8"))

    def list_summaries(self) -> list[dict]:
        if not self.index_path.exists():
            return []
        summaries = json.loads(self.index_path.read_text(encoding="utf-8"))
        return sorted(summaries, key=lambda s: s["created_at"], reverse=True)

    def _index_upsert(self, record: dict) -> None:
        summaries = self.list_summaries()
        summaries = [s for s in summaries if s["profile_id"] != record["profile_id"]]
        summaries.append({
            "profile_id": record["profile_id"],
            "created_at": record["created_at"],
            "owner_uid": record.get("owner_uid"),
            "household_id": record.get("household_id") or household_id_from_documents(record.get("documents")),
            "person_name": record.get("household", {}).get("person_name"),
            "document_count": len(record.get("documents", [])),
        })
        self.index_path.write_text(json.dumps(summaries, indent=2), encoding="utf-8")
