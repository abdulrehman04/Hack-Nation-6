"""Profile storage. One place chooses the backend, so it is easy to swap.

Set STORE_BACKEND to "firestore" (default) or "json". To add another backend,
write a ProfileStore and return it from get_store(); callers stay unchanged.
"""

from .. import config
from .base import ProfileStore
from .firestore_store import FirestoreProfileStore
from .json_store import JsonProfileStore

_store: ProfileStore | None = None


def get_store() -> ProfileStore:
    """Return the configured profile store."""
    global _store
    if _store is None:
        if config.STORE_BACKEND == "json":
            _store = JsonProfileStore(config.STORE_DIR)
        else:
            _store = FirestoreProfileStore(config.FIREBASE_PROJECT_ID, config.FIREBASE_API_KEY)
    return _store


__all__ = ["ProfileStore", "JsonProfileStore", "FirestoreProfileStore", "get_store"]
