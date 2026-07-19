"""Paths into the challenge data under data/. Override with REALDOOR_DATA."""

from __future__ import annotations

import os
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]

DATA_ROOT = Path(os.environ.get("REALDOOR_DATA", REPO_ROOT / "data"))

DOCUMENTS_DIR = DATA_ROOT / "documents"
DOCUMENT_GOLD = DATA_ROOT / "gold" / "document_gold.jsonl"
DOCUMENT_MANIFEST = DATA_ROOT / "gold" / "document_manifest.csv"
FIELD_SCHEMA = DATA_ROOT / "gold" / "field_schema.json"

MTSP_CSV = DATA_ROOT / "mtsp_2026_boston_cambridge_quincy.csv"
LIHTC_CSV = DATA_ROOT / "lihtc_boston_metro_subset.csv"
PROPERTY_DICTIONARY = DATA_ROOT / "property_data_dictionary.csv"

RULE_CORPUS = DATA_ROOT / "rule_corpus.jsonl"
QA_GOLD = DATA_ROOT / "qa_gold.jsonl"
ADVERSARIAL_TESTS = DATA_ROOT / "adversarial_tests.jsonl"
CHECKLISTS = DATA_ROOT / "application_checklists.json"

# Organizer schemas our output must validate against.
SCHEMAS_ROOT = REPO_ROOT / "schemas"
SUBMISSION_SCHEMA = SCHEMAS_ROOT / "submission.schema.json"
DOCUMENT_GOLD_SCHEMA = SCHEMAS_ROOT / "document_gold.schema.json"

# Where confirmed profiles are persisted (file-backed store; swap in config).
STORE_DIR = REPO_ROOT / "out" / "store"

# Stage 01 extraction output, consumed by Stage 02 (realdoor/rules).
EXTRACTION_OUTPUT = REPO_ROOT / "out" / "extraction_output.json"

# Stage 03 session-deletion tombstones (realdoor/packet). A household_id
# marked here is treated as deleted without mutating EXTRACTION_OUTPUT, which
# is shared demo data for every household.
SESSION_STORE_DIR = REPO_ROOT / "out" / "sessions"


def data_available() -> bool:
    """True when the vendored challenge data can be found."""
    return DOCUMENT_GOLD.exists()
