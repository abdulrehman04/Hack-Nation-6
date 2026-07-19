"""Tests for Stage 02: Phase 1 calculation engine and Phase 2 chat safety."""

import json
import os
import unittest
from unittest.mock import patch

from realdoor import config
from realdoor.rules import (
    annualize,
    cite,
    compare_to_threshold,
    detect_pay_stub_conflict,
    is_current,
    percent_of_threshold,
)
from realdoor.rules.pipeline import run_all
from realdoor.rules.qa import FALLBACK_MESSAGE, _cited_rule_ids, _flagged_words, answer_question, build_prompt

GOLD_PROFILES = {
    "HH-001": (56316.00, 72000, "below_or_equal", "READY_TO_REVIEW", []),
    "HH-002": (49920.00, 82320, "below_or_equal", "NEEDS_REVIEW", ["PAY_STUB_TOTAL_CONFLICT"]),
    "HH-003": (40230.00, 92580, "below_or_equal", "READY_TO_REVIEW", []),
    "HH-004": (51008.00, 102840, "below_or_equal", "NEEDS_REVIEW", ["GIG_INCOME_UNCORROBORATED"]),
    "HH-005": (45968.00, 111120, "below_or_equal", "NEEDS_REVIEW", ["EMPLOYMENT_LETTER_EXPIRED"]),
    "HH-006": (105000.00, 119340, "below_or_equal", "READY_TO_REVIEW", []),
}


class TestCalculate(unittest.TestCase):
    def test_annualize_biweekly(self):
        self.assertEqual(annualize(2166.0, "biweekly"), 56316.0)

    def test_annualize_rejects_unknown_frequency(self):
        with self.assertRaises(ValueError):
            annualize(100, "quarterly")

    def test_annualize_rejects_negative(self):
        with self.assertRaises(ValueError):
            annualize(-1, "weekly")

    def test_is_current_boundary(self):
        self.assertTrue(is_current("2026-05-19"))
        self.assertFalse(is_current("2026-05-18"))
        self.assertFalse(is_current(None))

    def test_pay_stub_conflict_detection(self):
        self.assertTrue(detect_pay_stub_conflict([72540.0, 49920.0]))
        self.assertFalse(detect_pay_stub_conflict([56316.0, 56316.0]))
        self.assertFalse(detect_pay_stub_conflict([56316.0]))

    def test_compare_to_threshold_household_size_1(self):
        comparison, threshold = compare_to_threshold(56316.0, 1)
        self.assertEqual(comparison, "below_or_equal")
        self.assertEqual(threshold, 72000.0)

    def test_compare_to_threshold_above(self):
        comparison, _ = compare_to_threshold(100000.0, 1)
        self.assertEqual(comparison, "above")

    def test_compare_to_threshold_no_frozen_threshold_over_8(self):
        comparison, threshold = compare_to_threshold(100000.0, 9)
        self.assertEqual(comparison, "no_frozen_threshold")
        self.assertIsNone(threshold)

    def test_percent_of_threshold(self):
        self.assertEqual(percent_of_threshold(56316.0, 72000.0), 78.2)


@unittest.skipUnless(config.data_available(), "challenge data not available")
class TestCorpus(unittest.TestCase):
    def test_cite_known_rule(self):
        citation = cite("CH-INCOME-001")
        self.assertEqual(citation["rule_id"], "CH-INCOME-001")
        self.assertIn("source_url", citation)
        self.assertIn("effective_date", citation)

    def test_cite_unknown_rule_raises(self):
        with self.assertRaises(KeyError):
            cite("NOT-A-RULE")


@unittest.skipUnless(
    config.data_available() and config.EXTRACTION_OUTPUT.exists(),
    "extraction output not available; run scripts/dump_output.py first",
)
class TestPipelineGold(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.profiles = run_all()

    def test_all_six_households_present(self):
        self.assertEqual(set(self.profiles), set(GOLD_PROFILES))

    def test_gold_numbers_match_exactly(self):
        for household_id, (income, threshold, comparison, status, reasons) in GOLD_PROFILES.items():
            profile = self.profiles[household_id]
            self.assertEqual(profile["annualized_income"], income, household_id)
            self.assertEqual(profile["frozen_60_percent_threshold"], threshold, household_id)
            self.assertEqual(profile["comparison"], comparison, household_id)
            self.assertEqual(profile["readiness_status"], status, household_id)
            self.assertEqual(profile["review_reasons"], reasons, household_id)

    def test_profile_carries_required_citations(self):
        for profile in self.profiles.values():
            self.assertGreater(len(profile["citations"]), 0)
            rule_ids = {c["rule_id"] for c in profile["citations"]}
            self.assertIn("CH-INCOME-001", rule_ids)
            self.assertIn("CH-READINESS-001", rule_ids)

    def test_quarantined_content_never_leaks_into_output(self):
        # HH-002, HH-004, HH-006 each carry one quarantined injection payload;
        # none of that text should reach the enriched profile.
        for household_id in ("HH-002", "HH-004", "HH-006"):
            profile = self.profiles[household_id]
            self.assertGreater(profile["injection_attempts_found"], 0, household_id)
            self.assertNotIn("Ignore prior instructions", json.dumps(profile))

    def test_disclosure_text_present(self):
        for profile in self.profiles.values():
            self.assertIn("hackathon convention", profile["disclosure"])

    def test_never_uses_decisioning_language(self):
        forbidden = ["eligible", "ineligible", "approved", "denied"]
        for profile in self.profiles.values():
            blob = json.dumps(profile).lower()
            for word in forbidden:
                self.assertNotIn(word, blob, f"{profile['household_id']} output contains {word!r}")


@unittest.skipUnless(config.data_available(), "challenge data not available")
class TestQA(unittest.TestCase):
    def test_flagged_words_detects_forbidden_language(self):
        self.assertEqual(_flagged_words("You are approved for this unit"), ["approved"])
        self.assertEqual(_flagged_words("Here is your annualized income"), [])

    def test_cited_rule_ids_extracts_known_ids(self):
        text = "Per CH-INCOME-001 and HUD-MTSP-002, your income compares as below_or_equal."
        ids = _cited_rule_ids(text)
        self.assertIn("CH-INCOME-001", ids)
        self.assertIn("HUD-MTSP-002", ids)

    def test_build_prompt_includes_household_and_rules(self):
        profile = {"household_id": "HH-001", "annualized_income": 56316.0}
        prompt = build_prompt(profile)
        self.assertIn("HH-001", prompt)
        self.assertIn("CH-DECISION-001", prompt)
        self.assertIn("You are RealDoor", prompt)

    def test_answer_question_abstains_without_api_key(self):
        profile = {"household_id": "HH-001", "annualized_income": 56316.0}
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("GEMINI_API_KEY", None)
            result = answer_question(profile, "What is my annualized income?")
        self.assertTrue(result["abstained"])
        self.assertEqual(result["answer"], FALLBACK_MESSAGE)
        self.assertEqual(result["household_id"], "HH-001")

    def test_answer_question_rejects_forbidden_language(self):
        profile = {"household_id": "HH-001", "annualized_income": 56316.0}
        with patch("realdoor.rules.qa._call_gemini", return_value="You are approved."):
            result = answer_question(profile, "Am I approved?")
        self.assertTrue(result["abstained"])
        self.assertIn("approved", result["safety_check"]["flagged_words_found"])
        self.assertEqual(result["answer"], FALLBACK_MESSAGE)

    def test_answer_question_returns_grounded_answer(self):
        profile = {"household_id": "HH-001", "annualized_income": 56316.0}
        grounded = "Per CH-INCOME-001, your annualized income is $56,316.00."
        with patch("realdoor.rules.qa._call_gemini", return_value=grounded):
            result = answer_question(profile, "What is my annualized income?")
        self.assertFalse(result["abstained"])
        self.assertEqual(result["answer"], grounded)
        self.assertIn("CH-INCOME-001", result["rule_ids_cited"])


if __name__ == "__main__":
    unittest.main()
