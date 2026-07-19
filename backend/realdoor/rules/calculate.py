"""Pure-Python arithmetic for Stage 02 Phase 1. Zero LLM calls, ever.

Every function here takes already-confirmed field values and returns a number,
a comparison, or a flag. Thresholds are loaded from config.MTSP_CSV; nothing
is hardcoded.
"""

from __future__ import annotations

import csv
from datetime import date, timedelta
from functools import lru_cache

from .. import config

FREQUENCY = {"weekly": 52, "biweekly": 26, "semimonthly": 24, "monthly": 12, "annual": 1}

ANCHOR_DATE = date(2026, 7, 18)
CURRENCY_WINDOW_DAYS = 60
CURRENCY_START = ANCHOR_DATE - timedelta(days=CURRENCY_WINDOW_DAYS)  # 2026-05-19

CURRENCY_DISCLOSURE = (
    "The 60-day currency window is a hackathon convention (CH-INCOME-001), "
    "not a universal LIHTC rule."
)

PAY_STUB_CONFLICT_PCT = 0.10


# Annualization

def annualize(amount: float, frequency: str) -> float:
    """Multiply a periodic amount by its frequency multiplier."""
    if frequency not in FREQUENCY:
        raise ValueError(f"Unsupported frequency: {frequency}")
    if amount < 0:
        raise ValueError("Amount must be non-negative")
    return round(float(amount) * FREQUENCY[frequency], 2)


def income_from_pay_stub(gross_pay: float, pay_frequency: str) -> float:
    return annualize(gross_pay, pay_frequency)


def income_from_employment_letter(weekly_hours: float, hourly_rate: float) -> float:
    if weekly_hours < 0 or hourly_rate < 0:
        raise ValueError("Values must be non-negative")
    return round(float(weekly_hours) * float(hourly_rate) * FREQUENCY["weekly"], 2)


def income_from_benefit_letter(monthly_benefit: float, benefit_frequency: str) -> float:
    return annualize(monthly_benefit, benefit_frequency)


def income_from_gig_statement(gross_receipts: float) -> float:
    return annualize(gross_receipts, "monthly")


# Currency (CH-INCOME-001 convention)

def is_current(document_date: str | None) -> bool:
    """A document is current if its date is on/after the 60-day currency start."""
    if not document_date:
        return False
    return document_date >= CURRENCY_START.isoformat()


# Conflict detection

def detect_pay_stub_conflict(annualized_amounts: list[float]) -> bool:
    """True when multiple pay-stub annualizations spread by more than 10% of the max."""
    if len(annualized_amounts) < 2:
        return False
    highest = max(annualized_amounts)
    lowest = min(annualized_amounts)
    return (highest - lowest) > (PAY_STUB_CONFLICT_PCT * highest)


# Threshold lookup (frozen MTSP 60% band)

@lru_cache(maxsize=1)
def load_mtsp_table() -> dict[int, dict]:
    """Load the frozen MTSP CSV, keyed by household_size (int)."""
    with config.MTSP_CSV.open(encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    return {int(row["household_size"]): row for row in rows}


def threshold_for_household_size(household_size: int) -> dict | None:
    """MTSP row for a household size, or None when no frozen threshold applies (size > 8)."""
    return load_mtsp_table().get(household_size)


def compare_to_threshold(annualized_income: float, household_size: int) -> tuple[str, float | None]:
    """Compare annualized income to the frozen 60% threshold for a household size.

    Returns (comparison, threshold): comparison is one of
    "below_or_equal", "above", "no_frozen_threshold".
    """
    row = threshold_for_household_size(household_size)
    if row is None:
        return "no_frozen_threshold", None
    threshold = float(row["core_challenge_threshold"])
    comparison = "below_or_equal" if annualized_income <= threshold else "above"
    return comparison, threshold


def percent_of_threshold(annualized_income: float, threshold: float) -> float:
    """Annualized income as a percentage of the threshold, rounded to one decimal."""
    if threshold <= 0:
        raise ValueError("Threshold must be positive")
    return round(annualized_income / threshold * 100, 1)
