"""Tests for the file-backed profile store."""

import tempfile
import unittest
from pathlib import Path

from realdoor.storage.json_store import JsonProfileStore

SAMPLE = {
    "household": {"person_name": "Test Renter", "household_size": "4"},
    "documents": [{"document_type": "pay_stub", "method": "ocr", "fields": []}],
    "sanity_issues": [],
}


class TestJsonProfileStore(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.store = JsonProfileStore(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_save_returns_id_and_stamps_record(self):
        pid = self.store.save(dict(SAMPLE))
        self.assertTrue(pid)
        record = self.store.get(pid)
        self.assertEqual(record["profile_id"], pid)
        self.assertEqual(record["status"], "confirmed")
        self.assertIn("created_at", record)
        self.assertEqual(record["household"]["person_name"], "Test Renter")

    def test_get_missing_returns_none(self):
        self.assertIsNone(self.store.get("does-not-exist"))

    def test_summaries_list_saved_profiles(self):
        self.store.save(dict(SAMPLE))
        self.store.save(dict(SAMPLE))
        summaries = self.store.list_summaries()
        self.assertEqual(len(summaries), 2)
        self.assertEqual(summaries[0]["person_name"], "Test Renter")
        self.assertEqual(summaries[0]["document_count"], 1)

    def test_files_written_to_disk(self):
        pid = self.store.save(dict(SAMPLE))
        self.assertTrue((Path(self.tmp.name) / "profiles" / f"{pid}.json").exists())
        self.assertTrue((Path(self.tmp.name) / "index.json").exists())


if __name__ == "__main__":
    unittest.main()
