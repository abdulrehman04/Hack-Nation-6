"""Stage 3: renter-controlled readiness packet.

Pipeline: checklist (missing/expired vs the gold checklist) -> builder
(assemble the exportable packet; delete session data). The renter previews,
downloads, and can delete everything; nothing here is ever auto-sent.
"""

from .builder import (
    DeletedSessionStore,
    build_packet,
    delete_session,
    get_session_store,
    is_session_deleted,
)
from .checklist import build_checklist, load_required_document_types

__all__ = [
    "build_checklist",
    "load_required_document_types",
    "build_packet",
    "delete_session",
    "is_session_deleted",
    "get_session_store",
    "DeletedSessionStore",
]
