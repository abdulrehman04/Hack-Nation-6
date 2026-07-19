"""Convert the gold JSONL into one pretty JSON array and save it.

    python scripts/dump_gold.py           # writes out/gold_pretty.json

The output is a JSON list of gold document records (indented), for reference
and for diffing against out/extraction_output.json.
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from realdoor import config  # noqa: E402

OUT = config.REPO_ROOT / "out"


def main() -> None:
    if not config.DOCUMENT_GOLD.exists():
        sys.exit(f"Gold not found at {config.DOCUMENT_GOLD}. Set REALDOOR_DATA.")
    with config.DOCUMENT_GOLD.open(encoding="utf-8") as f:
        rows = [json.loads(x) for x in f if x.strip()]

    OUT.mkdir(exist_ok=True)
    path = OUT / "gold_pretty.json"
    path.write_text(json.dumps(rows, indent=2), encoding="utf-8")
    print(f"Wrote {len(rows)} gold records to {path}")


if __name__ == "__main__":
    main()
