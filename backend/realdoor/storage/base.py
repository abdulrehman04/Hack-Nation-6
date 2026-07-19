"""Storage interface for confirmed profiles.

Swap the implementation (JSON files now, a real database later) without touching
the callers. Records are plain dicts so no storage backend leaks into the API.
"""

from __future__ import annotations

import re
from abc import ABC, abstractmethod


def household_id_from_documents(documents: list | None) -> str | None:
    """Derive an hh-XXX household id from document file names (uppercased)."""
    for doc in documents or []:
        match = re.match(r"(hh-\d+)", str(doc.get("file_name") or ""), re.IGNORECASE)
        if match:
            return match.group(1).upper()
    return None


class ProfileStore(ABC):
    """A place to persist and read back confirmed profiles."""

    @abstractmethod
    def save(self, profile: dict) -> str:
        """Persist a profile and return its id."""

    @abstractmethod
    def get(self, profile_id: str) -> dict | None:
        """Return the full profile record, or None if it does not exist."""

    @abstractmethod
    def list_summaries(self) -> list[dict]:
        """Return lightweight summaries of all stored profiles, newest first."""

    @abstractmethod
    def delete(self, profile_id: str) -> bool:
        """Remove a profile. Return True if it existed, False otherwise."""
