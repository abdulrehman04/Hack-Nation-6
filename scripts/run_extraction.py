"""Smoke-test the extraction layer against the pack's gold boxes.

Runs a digital document and a rasterized one, then checks that the tokens we
locate fall on each gold field's source box, and prints overall coverage.

    python scripts/run_extraction.py
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from realdoor import config  # noqa: E402
from realdoor.extraction.readers import extract_document, tokens_in_box  # noqa: E402


def load_gold() -> dict:
    rows = {}
    for line in config.DOCUMENT_GOLD.open(encoding="utf-8"):
        if line.strip():
            r = json.loads(line)
            rows[r["document_id"]] = r
    return rows


def show_field_hits(doc_id: str, gold: dict) -> None:
    rec = gold[doc_id]
    result = extract_document(config.DOCUMENTS_DIR / rec["file_name"])
    print(f"\n=== {doc_id}  ({rec['document_type']}, method={result.method}, "
          f"{len(result.tokens)} tokens) ===")
    for field in rec["fields"]:
        hits = tokens_in_box(result.tokens, tuple(field["bbox"]))
        found = " ".join(t.text for t in hits)
        status = "OK " if hits else "MISS"
        print(f"  [{status}] {field['field']:<22} gold={field['value']!r:<36} found={found!r}")


def coverage_summary(gold: dict) -> None:
    total = hit = 0
    by_method: dict[str, int] = {}
    for rec in gold.values():
        result = extract_document(config.DOCUMENTS_DIR / rec["file_name"])
        by_method[result.method] = by_method.get(result.method, 0) + 1
        for field in rec["fields"]:
            total += 1
            if tokens_in_box(result.tokens, tuple(field["bbox"])):
                hit += 1
    print(f"\n=== Gold-box coverage across {len(gold)} docs ===")
    print(f"  fields located: {hit}/{total} ({100 * hit / total:.1f}%)")
    print(f"  method mix: {by_method}")


def main() -> None:
    if not config.data_available():
        sys.exit(f"Challenge data not found at {config.DATA_ROOT}. Set REALDOOR_DATA.")
    gold = load_gold()
    show_field_hits("HH-001-D01", gold)  # digital / text layer
    show_field_hits("HH-001-D02", gold)  # rasterized / OCR
    coverage_summary(gold)


if __name__ == "__main__":
    main()
