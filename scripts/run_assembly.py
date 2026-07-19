"""Score assembled fields against the pack's gold across all 24 documents.

    python scripts/run_assembly.py
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from realdoor import config  # noqa: E402
from realdoor.extraction.assembly import assemble  # noqa: E402
from realdoor.extraction.readers import extract_document  # noqa: E402


def load_gold() -> list[dict]:
    return [json.loads(x) for x in config.DOCUMENT_GOLD.open(encoding="utf-8") if x.strip()]


def values_match(got, want) -> bool:
    if isinstance(want, float) or isinstance(got, float):
        try:
            return abs(float(got) - float(want)) < 0.01
        except (TypeError, ValueError):
            return False
    return got == want


def main() -> None:
    if not config.data_available():
        sys.exit(f"Challenge data not found at {config.DATA_ROOT}. Set REALDOOR_DATA.")

    total = correct = 0
    injection_docs = injection_caught = 0

    for rec in load_gold():
        doc = extract_document(config.DOCUMENTS_DIR / rec["file_name"])
        result = assemble(doc, rec["document_type"])
        got = {f.name: f for f in result.fields}
        gold_fields = {f["field"]: f["value"] for f in rec["fields"]}

        misses = []
        for name, want in gold_fields.items():
            total += 1
            field = got.get(name)
            if field is not None and field.status in ("extracted", "quarantined") \
                    and values_match(field.value, want):
                correct += 1
            else:
                have = field.value if field else "<missing>"
                misses.append(f"{name}: got {have!r} want {want!r}")

        if rec.get("contains_adversarial_text"):
            injection_docs += 1
            if result.injected_instruction:
                injection_caught += 1

        flag = "" if not misses else "  <-- " + " | ".join(misses)
        print(f"{rec['document_id']:<12} {rec['document_type']:<20} "
              f"method={result.method:<10} {len(gold_fields) - len(misses)}/{len(gold_fields)}{flag}")

    print(f"\nField accuracy: {correct}/{total} ({100 * correct / total:.1f}%)")
    print(f"Injection docs quarantined: {injection_caught}/{injection_docs}")


if __name__ == "__main__":
    main()
