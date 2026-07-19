"""RealDoor application-readiness copilot. Assistive, never adjudicative.

Stages (see CLAUDE.md for the full requirements):
    extraction  Stage 1: read documents into confirmed fields   [built]
    rules       Stage 2: cited rules and math                   [stub]
    packet      Stage 3: renter-controlled packet               [stub]
    safety      refusal, privacy, deletion                      [stub]

It extracts, cites, and computes. It never decides eligibility.
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
