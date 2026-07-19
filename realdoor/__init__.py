"""RealDoor application-readiness copilot — assistive, never adjudicative.

Stages (see CLAUDE.md for the full requirements):
    extraction  Stage 1 — extract documents into confirmed fields  [built]
    rules       Stage 2 — cited rules + deterministic math          [to build]
    packet      Stage 3 — renter-controlled readiness packet        [to build]
    safety      cross-cutting refusal / privacy / deletion          [to build]

This system extracts, cites, and computes; it never decides eligibility.
"""

from .extraction import (
    AssembledDocument,
    ExtractedDocument,
    Field,
    Token,
    assemble,
    extract_document,
)

__all__ = [
    "Token",
    "ExtractedDocument",
    "extract_document",
    "Field",
    "AssembledDocument",
    "assemble",
]
