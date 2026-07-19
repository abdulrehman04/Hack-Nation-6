"""Run the Stage 02 Phase 1 pipeline for all six households and print results.

    python scripts/run_rules.py

Writes out/understand_output.json and checks each household against the gold
numbers in data/application_checklists.json.
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from realdoor import config  # noqa: E402
from realdoor.rules import run_all  # noqa: E402

OUT = config.REPO_ROOT / "out"

GOLD = {
    "HH-001": (56316.00, 72000, "below_or_equal", "READY_TO_REVIEW", []),
    "HH-002": (49920.00, 82320, "below_or_equal", "NEEDS_REVIEW", ["PAY_STUB_TOTAL_CONFLICT"]),
    "HH-003": (40230.00, 92580, "below_or_equal", "READY_TO_REVIEW", []),
    "HH-004": (51008.00, 102840, "below_or_equal", "NEEDS_REVIEW", ["GIG_INCOME_UNCORROBORATED"]),
    "HH-005": (45968.00, 111120, "below_or_equal", "NEEDS_REVIEW", ["EMPLOYMENT_LETTER_EXPIRED"]),
    "HH-006": (105000.00, 119340, "below_or_equal", "READY_TO_REVIEW", []),
}


def main() -> None:
    if not config.data_available():
        sys.exit(f"Challenge data not found at {config.DATA_ROOT}. Set REALDOOR_DATA.")
    if not config.EXTRACTION_OUTPUT.exists():
        sys.exit(
            f"Extraction output not found at {config.EXTRACTION_OUTPUT}. "
            "Run scripts/dump_output.py first."
        )

    profiles = run_all()

    all_pass = True
    for household_id in sorted(profiles):
        profile = profiles[household_id]
        print(f"\n{household_id}: {profile['person_name']} (size {profile['household_size']})")
        print(f"  annualized_income = {profile['annualized_income']}")
        print(f"  frozen_60_percent_threshold = {profile['frozen_60_percent_threshold']}")
        print(f"  comparison = {profile['comparison']}")
        print(f"  readiness_status = {profile['readiness_status']}")
        print(f"  review_reasons = {profile['review_reasons']}")
        print(f"  injection_attempts_found = {profile['injection_attempts_found']}")

        expected = GOLD.get(household_id)
        if expected:
            income, threshold, comparison, status, reasons = expected
            ok = (profile["annualized_income"] == income
                  and profile["frozen_60_percent_threshold"] == threshold
                  and profile["comparison"] == comparison
                  and profile["readiness_status"] == status
                  and profile["review_reasons"] == reasons)
            all_pass = all_pass and ok
            print(f"  gold check: {'PASS' if ok else 'FAIL'}")

    OUT.mkdir(exist_ok=True)
    path = OUT / "understand_output.json"
    path.write_text(json.dumps(profiles, indent=2), encoding="utf-8")
    print(f"\nWrote {len(profiles)} enriched profiles to {path}")

    if all_pass:
        print("ALL GOLD HOUSEHOLDS PASS")
    else:
        print("GOLD MISMATCH -- see FAIL rows above")
        sys.exit(1)


if __name__ == "__main__":
    main()
