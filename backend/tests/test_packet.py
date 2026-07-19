"""Tests for Stage 03: document checklist, packet assembly, and session deletion."""

import json
import tempfile
import unittest

from realdoor import config
from realdoor.packet import build_checklist, build_packet, delete_session, is_session_deleted
from realdoor.packet import builder as builder_module
from realdoor.rules import build_profile, load_households

_DATA_READY = config.data_available() and config.EXTRACTION_OUTPUT.exists()
_SKIP_REASON = "extraction output not available; run scripts/dump_output.py first"


@unittest.skipUnless(_DATA_READY, _SKIP_REASON)
class TestChecklist(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.households = load_households()

    def _rows(self, household_id: str) -> dict:
        result = build_checklist(household_id, self.households[household_id])
        return {row["document_type"]: row for row in result["checklist"]}

    def test_HH001_all_present(self):
        rows = self._rows("HH-001")
        self.assertEqual(rows["application_summary"]["status"], "PRESENT_AND_CURRENT")
        self.assertEqual(rows["pay_stub"]["status"], "PRESENT_AND_CURRENT")
        self.assertEqual(rows["employment_letter"]["status"], "PRESENT_AND_CURRENT")
        self.assertEqual(rows["benefit_letter"]["status"], "NOT_PROVIDED_OPTIONAL")
        self.assertEqual(rows["gig_statement"]["status"], "NOT_PROVIDED_OPTIONAL")

    def test_HH003_missing_employment_letter(self):
        rows = self._rows("HH-003")
        # employment_letter is technically required, but a current pay_stub and
        # benefit_letter substitute for it as income evidence (mirrors pipeline.py's
        # MISSING_REQUIRED_EVIDENCE rule), so it is not a blocking gap here.
        self.assertEqual(rows["employment_letter"]["status"], "NOT_PROVIDED_OPTIONAL")
        self.assertNotEqual(rows["employment_letter"]["status"], "MISSING_REQUIRED")

    def test_HH004_missing_gig_corroboration(self):
        rows = self._rows("HH-004")
        self.assertIn("gig_income_corroboration", rows)
        self.assertEqual(rows["gig_income_corroboration"]["status"], "MISSING_REQUIRED")
        self.assertFalse(rows["gig_income_corroboration"]["optional"])

    def test_HH005_expired_employment_letter(self):
        rows = self._rows("HH-005")
        self.assertEqual(rows["employment_letter"]["status"], "PRESENT_BUT_EXPIRED")

    def test_checklist_message_strings(self):
        rows1 = self._rows("HH-001")
        self.assertEqual(
            rows1["application_summary"]["message"], "1 document(s) on file, current and consistent."
        )
        self.assertEqual(rows1["pay_stub"]["message"], "2 document(s) on file, current and consistent.")
        self.assertEqual(
            rows1["benefit_letter"]["message"], "Not provided (optional / only if applicable)."
        )

        rows5 = self._rows("HH-005")
        self.assertEqual(
            rows5["employment_letter"]["message"],
            "1 document(s) on file but expired (outside 60-day window).",
        )

        rows4 = self._rows("HH-004")
        self.assertEqual(
            rows4["gig_income_corroboration"]["message"], "Required — not found in submitted documents."
        )


@unittest.skipUnless(_DATA_READY, _SKIP_REASON)
class TestPacketBuilder(unittest.TestCase):
    def setUp(self):
        # Redirect the session-deletion tombstone at a temp dir so these tests
        # never touch the real out/sessions/ store shared with the live app.
        self.tmp = tempfile.TemporaryDirectory()
        self._original_store = builder_module._session_store
        builder_module._session_store = builder_module.DeletedSessionStore(self.tmp.name)

    def tearDown(self):
        builder_module._session_store = self._original_store
        self.tmp.cleanup()

    def _packet_for(self, household_id: str) -> dict:
        documents = load_households()[household_id]
        profile = build_profile(household_id, documents)
        checklist = build_checklist(household_id, documents)["checklist"]
        return build_packet(household_id, profile, checklist)

    def test_packet_contains_disclaimer(self):
        packet = self._packet_for("HH-001")
        self.assertIn("disclaimer", packet)
        self.assertIn("CH-DECISION-001", packet["disclaimer"])

    def test_packet_contains_submission_schema_output(self):
        packet = self._packet_for("HH-001")
        schema = json.loads(config.SUBMISSION_SCHEMA.read_text(encoding="utf-8"))
        sub = packet["submission_schema_output"]
        for key in schema["required"]:
            self.assertIn(key, sub)
        self.assertGreaterEqual(sub["annualized_income"], 0)
        self.assertIn(sub["comparison"], schema["properties"]["comparison"]["enum"])
        self.assertIn(sub["readiness_status"], schema["properties"]["readiness_status"]["enum"])
        self.assertIsInstance(sub["citations"], list)

    def test_packet_no_eligibility_language(self):
        forbidden = ["eligible", "approved", "denied", "ineligible", "accepted", "rejected"]
        for household_id in ("HH-001", "HH-002", "HH-003", "HH-004", "HH-005", "HH-006"):
            blob = json.dumps(self._packet_for(household_id)).lower()
            for word in forbidden:
                self.assertNotIn(word, blob, f"{household_id} packet contains {word!r}")

    def test_session_deletion_removes_household_data(self):
        self.assertFalse(is_session_deleted("HH-001"))
        result = delete_session("HH-001")
        self.assertTrue(result["deleted"])
        self.assertEqual(result["household_id"], "HH-001")
        self.assertIn("extraction_data", result["items_deleted"])
        self.assertTrue(is_session_deleted("HH-001"))

    def test_session_deletion_preserves_other_households(self):
        delete_session("HH-001")
        self.assertTrue(is_session_deleted("HH-001"))
        self.assertFalse(is_session_deleted("HH-002"))


if __name__ == "__main__":
    unittest.main()
