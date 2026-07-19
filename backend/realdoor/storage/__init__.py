"""Profile storage. One place chooses the backend, so it is easy to swap.

To move off JSON files, write another ProfileStore and return it from
get_store(); callers stay unchanged.
"""

from .. import config
from .base import ProfileStore
from .json_store import JsonProfileStore

_store: ProfileStore | None = None


def get_store() -> ProfileStore:
    """Return the configured profile store (a JSON-file store for now)."""
    global _store
    if _store is None:
        _store = JsonProfileStore(config.STORE_DIR)
    return _store


__all__ = ["ProfileStore", "JsonProfileStore", "get_store"]
