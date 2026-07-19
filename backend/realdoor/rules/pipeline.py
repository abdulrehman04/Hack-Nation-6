"""Phase 1 pipeline: orchestrate calculation across one household's documents.

Reads Stage 01 output via grouper, runs the arithmetic in calculate.py, and
assembles the enriched profile that Phase 2 (qa.py) and the /api/understand
endpoint consume. Zero LLM calls in this module.
"""

from __future__ import annotations

from datetime import datetime, timezone

from . import calculate, corpus
from .grouper import Document, load_households

PHASE = "stage02_phase1"

INCOME_RULE_ID = "CH-INCOME-001"
THRESHOLD_RULE_ID = "HUD-MTSP-002"
READINESS_RULE_ID = "CH-READINESS-001"


def _income_entry(
    doc: Document, cited_field: str, gross_amount, frequency: str, multiplier: int,
    annualized: float, document_date, counted: bool,
) -> dict:
    """Build one income_sources entry, citation included."""
    citation = doc.citation(cited_field) or {
        "document_id": doc.document_id, "file_name": doc.file_name, "page": None, "bbox": None,
    }
    return {
        "document_id": doc.document_id,
        "file_name": doc.file_name,
        "document_type": doc.document_type,
        "gross_amount": gross_amount,
        "frequency": frequency,
        "multiplier": multiplier,
        "annualized": annualized,
        "is_current": calculate.is_current(document_date),
        "document_date": document_date,
        "counted_in_total": counted,
        "citation": {**citation, "rule_id": INCOME_RULE_ID},
    }


def build_profile(household_id: str, documents: list[Document]) -> dict:
    """Run Phase 1 for one household's documents and return its enriched profile."""
    app_summary = next((d for d in documents if d.document_type == "application_summary"), None)
    person_name = app_summary.value("person_name") if app_summary else None
    household_size = app_summary.value("household_size") if app_summary else None
    address = app_summary.value("address") if app_summary else None
    application_date = app_summary.value("application_date") if app_summary else None

    pay_stubs = [d for d in documents if d.document_type == "pay_stub"]
    employment_letters = [d for d in documents if d.document_type == "employment_letter"]
    benefit_letters = [d for d in documents if d.document_type == "benefit_letter"]
    gig_statements = [d for d in documents if d.document_type == "gig_statement"]

    income_sources: list[dict] = []
    calculation_steps: list[str] = []
    review_reasons: list[str] = []
    wage_annualized = 0.0
    has_current_wage_evidence = False

    if pay_stubs:
        stub_amounts = []
        for doc in pay_stubs:
            gross_pay = doc.value("gross_pay")
            pay_frequency = doc.value("pay_frequency")
            pay_date = doc.value("pay_date")
            annualized = calculate.income_from_pay_stub(gross_pay, pay_frequency)
            stub_amounts.append(annualized)
            income_sources.append(_income_entry(
                doc, "gross_pay", gross_pay, pay_frequency, calculate.FREQUENCY[pay_frequency],
                annualized, pay_date, counted=True,
            ))
            calculation_steps.append(
                f"{doc.document_id}: pay_stub {gross_pay} x {calculate.FREQUENCY[pay_frequency]} "
                f"({pay_frequency}) = {annualized}"
            )
            if calculate.is_current(pay_date):
                has_current_wage_evidence = True

        if calculate.detect_pay_stub_conflict(stub_amounts):
            review_reasons.append("PAY_STUB_TOTAL_CONFLICT")
            wage_annualized = min(stub_amounts)
            calculation_steps.append(
                f"Pay stub totals conflict by more than {calculate.PAY_STUB_CONFLICT_PCT:.0%} of the max; "
                f"using the lower annualized value {wage_annualized}"
            )
        else:
            wage_annualized = stub_amounts[0]
    elif employment_letters:
        doc = employment_letters[0]
        weekly_hours = doc.value("weekly_hours")
        hourly_rate = doc.value("hourly_rate")
        document_date = doc.value("document_date")
        wage_annualized = calculate.income_from_employment_letter(weekly_hours, hourly_rate)
        income_sources.append(_income_entry(
            doc, "hourly_rate", hourly_rate, "weekly", calculate.FREQUENCY["weekly"],
            wage_annualized, document_date, counted=True,
        ))
        calculation_steps.append(
            f"{doc.document_id}: employment_letter {weekly_hours}h x {hourly_rate} x 52 = {wage_annualized}"
        )
        if calculate.is_current(document_date):
            has_current_wage_evidence = True

    for doc in employment_letters:
        document_date = doc.value("document_date")
        if pay_stubs:
            # A pay stub already covers this job's wage income; the letter corroborates
            # it (and is checked for currency below) but is not added to the total.
            weekly_hours = doc.value("weekly_hours")
            hourly_rate = doc.value("hourly_rate")
            annualized = calculate.income_from_employment_letter(weekly_hours, hourly_rate)
            income_sources.append(_income_entry(
                doc, "hourly_rate", hourly_rate, "weekly", calculate.FREQUENCY["weekly"],
                annualized, document_date, counted=False,
            ))
            calculation_steps.append(
                f"{doc.document_id}: employment_letter corroborates pay stub wage income; not added to total"
            )
        if not calculate.is_current(document_date):
            review_reasons.append("EMPLOYMENT_LETTER_EXPIRED")
            calculation_steps.append(
                f"{doc.document_id}: employment_letter dated {document_date} is before the currency "
                f"window start {calculate.CURRENCY_START.isoformat()}"
            )

    if not employment_letters:
        has_current_benefit = any(calculate.is_current(d.value("document_date")) for d in benefit_letters)
        if not (has_current_wage_evidence or has_current_benefit):
            review_reasons.append("MISSING_REQUIRED_EVIDENCE")
            calculation_steps.append("No employment_letter and no other current income evidence present")

    benefit_total = 0.0
    for doc in benefit_letters:
        monthly_benefit = doc.value("monthly_benefit")
        benefit_frequency = doc.value("benefit_frequency")
        document_date = doc.value("document_date")
        annualized = calculate.income_from_benefit_letter(monthly_benefit, benefit_frequency)
        benefit_total += annualized
        income_sources.append(_income_entry(
            doc, "monthly_benefit", monthly_benefit, benefit_frequency, calculate.FREQUENCY[benefit_frequency],
            annualized, document_date, counted=True,
        ))
        calculation_steps.append(
            f"{doc.document_id}: benefit_letter {monthly_benefit} x {calculate.FREQUENCY[benefit_frequency]} "
            f"({benefit_frequency}) = {annualized}"
        )

    gig_total = 0.0
    for doc in gig_statements:
        gross_receipts = doc.value("gross_receipts")
        annualized = calculate.income_from_gig_statement(gross_receipts)
        gig_total += annualized
        income_sources.append(_income_entry(
            doc, "gross_receipts", gross_receipts, "monthly", calculate.FREQUENCY["monthly"],
            annualized, None, counted=True,
        ))
        calculation_steps.append(f"{doc.document_id}: gig_statement {gross_receipts} x 12 = {annualized}")
        calculation_steps.append(f"{doc.document_id}: gig income is always flagged uncorroborated")
        review_reasons.append("GIG_INCOME_UNCORROBORATED")

    annualized_income = round(wage_annualized + benefit_total + gig_total, 2)
    calculation_steps.append(f"Annualized income = {annualized_income}")

    comparison, threshold = calculate.compare_to_threshold(annualized_income, household_size)
    threshold_pct = calculate.percent_of_threshold(annualized_income, threshold) if threshold else None
    if threshold is not None:
        calculation_steps.append(
            f"Frozen 60% threshold for household size {household_size} (HUD-MTSP-002): {threshold}"
        )
        calculation_steps.append(f"Comparison: {annualized_income} vs {threshold} -> {comparison}")
    else:
        calculation_steps.append(f"No frozen threshold available for household size {household_size}")

    # Injection attempts are already neutralized by Stage 01 (quarantined, never read above);
    # reported for audit only and never treated as a readiness flag.
    injection_attempts_found = sum(d.quarantined_count for d in documents)

    review_reasons = list(dict.fromkeys(review_reasons))
    readiness_status = "NEEDS_REVIEW" if review_reasons else "READY_TO_REVIEW"
    calculation_steps.append(f"Readiness: {readiness_status} ({review_reasons or 'no flags'})")

    rule_ids_used = [INCOME_RULE_ID]
    if threshold is not None:
        rule_ids_used.append(THRESHOLD_RULE_ID)
    rule_ids_used.append(READINESS_RULE_ID)
    citations = [corpus.cite(rule_id) for rule_id in rule_ids_used]

    return {
        "household_id": household_id,
        "household_size": household_size,
        "person_name": person_name,
        "address": address,
        "application_date": application_date,
        "documents_processed": len(documents),
        "income_sources": income_sources,
        "annualized_income": annualized_income,
        "frozen_60_percent_threshold": threshold,
        "comparison": comparison,
        "threshold_pct_used": threshold_pct,
        "readiness_status": readiness_status,
        "review_reasons": review_reasons,
        "injection_attempts_found": injection_attempts_found,
        "citations": citations,
        "calculation_steps": calculation_steps,
        "rule_versions_used": rule_ids_used,
        "disclosure": calculate.CURRENCY_DISCLOSURE,
        "processed_at": datetime.now(timezone.utc).isoformat(),
        "phase": PHASE,
    }


def run_household(household_id: str, path=None) -> dict:
    """Load extraction output, group by household, and build one profile."""
    households = load_households(path)
    if household_id not in households:
        raise KeyError(f"Unknown household_id: {household_id}")
    return build_profile(household_id, households[household_id])


def run_all(path=None) -> dict[str, dict]:
    """Build enriched profiles for every household in the extraction output."""
    households = load_households(path)
    return {hh_id: build_profile(hh_id, docs) for hh_id, docs in households.items()}
