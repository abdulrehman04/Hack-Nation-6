"""Load the frozen LIHTC property subset into typed records for the Discover UI.

Every record carries its own provenance (source URL, retrieval time, quality
flags) and an explicit "availability unknown" marker. Order is neutral
(alphabetical by name); the code never scores or ranks.
"""

from __future__ import annotations

import csv

from .. import config

# Shown verbatim in the UI so the renter is never misled about what this data is.
AVAILABILITY_NOTICE = (
    "Availability is unknown. This public record lists a property's location and "
    "unit mix only — it is not a vacancy listing and does not mean any unit is open."
)
DATA_NOTICE = (
    "Public HUD LIHTC data, shown as-is. RealDoor does not rank, recommend, verify, "
    "or contact any property. Blank quality flags mean no automated warning, not "
    "guaranteed accuracy."
)


def _int_or_none(raw: str | None):
    """Parse an integer cell, tolerating blanks the HUD export leaves empty."""
    if raw is None or raw.strip() == "":
        return None
    try:
        return int(raw)
    except ValueError:
        return None


def _float_or_none(raw: str | None):
    if raw is None or raw.strip() == "":
        return None
    try:
        return float(raw)
    except ValueError:
        return None


def _to_property(row: dict) -> dict:
    """Map one CSV row to the typed record the API returns; no interpretation added."""
    return {
        "hud_id": row["hud_id"],
        "project_name": row["project_name"],
        "address": row["project_address"],
        "city": row["project_city"],
        "state": row["project_state"],
        "zip": row["project_zip"],
        "total_units": _int_or_none(row["total_units"]),
        "low_income_units": _int_or_none(row["low_income_units"]),
        "bedrooms": {
            "studio": _int_or_none(row["studio_units"]) or 0,
            "one": _int_or_none(row["one_bedroom_units"]) or 0,
            "two": _int_or_none(row["two_bedroom_units"]) or 0,
            "three": _int_or_none(row["three_bedroom_units"]) or 0,
            "four": _int_or_none(row["four_bedroom_units"]) or 0,
        },
        "year_placed_in_service": row["year_placed_in_service"],
        "year_allocated": row["year_allocated"],
        "latitude": _float_or_none(row["latitude"]),
        "longitude": _float_or_none(row["longitude"]),
        "geocode_precision_code": row["geocode_precision_code"],
        "cbsa_name": row["cbsa_name"],
        "data_quality_flags": [f for f in (row["data_quality_flags"] or "").split("|") if f],
        "source_url": row["source_url"],
        "retrieved_utc": row["retrieved_utc"],
        "availability": "unknown",
    }


def load_properties() -> list[dict]:
    """Return every property in the frozen subset, alphabetical by name (neutral order)."""
    with config.LIHTC_CSV.open(encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    properties = [_to_property(row) for row in rows]
    properties.sort(key=lambda p: p["project_name"])
    return properties
