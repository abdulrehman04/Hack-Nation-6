"""Stage 2: cited rules and deterministic math.

Pipeline: grouper -> calculate -> pipeline (Phase 1, pure Python) -> qa (Phase
2, Gemini-grounded chat). The renter's confirmed Stage 1 fields are annualized,
compared against the frozen MTSP threshold, and checked for readiness; nothing
here decides eligibility.
"""

from .calculate import (
    CURRENCY_DISCLOSURE,
    CURRENCY_START,
    FREQUENCY,
    annualize,
    compare_to_threshold,
    detect_pay_stub_conflict,
    income_from_benefit_letter,
    income_from_employment_letter,
    income_from_gig_statement,
    income_from_pay_stub,
    is_current,
    percent_of_threshold,
)
from .corpus import cite, get_rules, load_rules
from .grouper import (
    Document,
    documents_from_confirmed,
    group_by_household,
    load_documents,
    load_households,
)
from .pipeline import build_profile, run_all, run_household
from .qa import FALLBACK_MESSAGE, answer_question, build_prompt

__all__ = [
    "FREQUENCY",
    "CURRENCY_START",
    "CURRENCY_DISCLOSURE",
    "annualize",
    "income_from_pay_stub",
    "income_from_employment_letter",
    "income_from_benefit_letter",
    "income_from_gig_statement",
    "is_current",
    "detect_pay_stub_conflict",
    "compare_to_threshold",
    "percent_of_threshold",
    "load_rules",
    "get_rules",
    "cite",
    "Document",
    "documents_from_confirmed",
    "load_documents",
    "group_by_household",
    "load_households",
    "build_profile",
    "run_household",
    "run_all",
    "answer_question",
    "build_prompt",
    "FALLBACK_MESSAGE",
]
