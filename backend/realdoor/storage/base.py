"""Storage interface for confirmed profiles.

Swap the implementation (JSON files now, a real database later) without touching
the callers. Records are plain dicts so no storage backend leaks into the API.
"""

from __future__ import annotations

from abc import ABC, abstractmethod


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
