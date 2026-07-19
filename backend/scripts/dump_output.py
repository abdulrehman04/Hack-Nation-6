"""Assemble every document into the gold schema and save pretty JSON.

Reads the file list from the manifest, assembles each document, serializes it
into the exact gold record schema, and verifies our output carries every gold
key. Writes out/extraction_output.json (a JSON list, indented).

    python scripts/dump_output.py

Compare against out/gold_pretty.json (from scripts/dump_gold.py).
"""

import csv
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from realdoor import config  # noqa: E402
from realdoor.extraction.assembly import assemble  # noqa: E402
from realdoor.extraction.readers import extract_document  # noqa: E402
from realdoor.extraction.serialize import (  # noqa: E402
    GOLD_FIELD_KEYS,
    GOLD_TOP_KEYS,
    to_gold_record,
)

OUT = config.REPO_ROOT / "out"


def load_manifest() -> list[dict]:
    with config.DOCUMENT_MANIFEST.open(encoding="utf-8") as f:
        return list(csv.DictReader(f))


def check_keys(record: dict) -> list[str]:
    """Return gold keys missing from our record (top-level and per-field)."""
    missing = [k for k in GOLD_TOP_KEYS if k not in record]
    for field in record["fields"]:
        missing += [f"fields.{k}" for k in GOLD_FIELD_KEYS if k not in field]
    return missing


def main() -> None:
    if not config.data_available():
        sys.exit(f"Challenge data not found at {config.DATA_ROOT}. Set REALDOOR_DATA.")

    records = []
    all_missing = []
    for entry in load_manifest():
        extracted = extract_document(config.DOCUMENTS_DIR / entry["file_name"])
        assembled = assemble(extracted, entry["document_type"])
        record = to_gold_record(
            entry["document_id"], entry["household_id"], entry["file_name"],
            extracted, assembled,
        )
        missing = check_keys(record)
        if missing:
            all_missing.append((entry["document_id"], missing))
        records.append(record)

    OUT.mkdir(exist_ok=True)
    path = OUT / "extraction_output.json"
    path.write_text(json.dumps(records, indent=2), encoding="utf-8")

    print(f"Wrote {len(records)} records to {path}")
    if all_missing:
        print("MISSING gold keys:")
        for doc_id, keys in all_missing:
            print(f"  {doc_id}: {keys}")
    else:
        print("Key parity: every record carries all gold keys "
              f"({GOLD_TOP_KEYS} / fields {GOLD_FIELD_KEYS}) ✓")


if __name__ == "__main__":
    main()
