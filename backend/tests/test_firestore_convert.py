"""Tests for the Firestore value conversion (no network)."""

import unittest

from realdoor.storage.firestore_store import from_fields, to_fields


class TestFirestoreConversion(unittest.TestCase):
    def test_roundtrip_preserves_nested_record(self):
        record = {
            "profile_id": "abc123",
            "status": "confirmed",
            "household": {"person_name": "Mara North", "household_size": "1"},
            "documents": [
                {
                    "document_type": "pay_stub",
                    "method": "ocr",
                    "fields": [
                        {"name": "gross_pay", "value": "2166.0", "confidence": 0.96, "reviewed": True},
                    ],
                },
            ],
            "sanity_issues": [],
        }
        restored = from_fields(to_fields(record))
        self.assertEqual(restored, record)

    def test_types_are_tagged(self):
        fields = to_fields({"s": "x", "n": 4, "f": 1.5, "b": True, "z": None, "a": [1, 2]})
        self.assertEqual(fields["s"], {"stringValue": "x"})
        self.assertEqual(fields["n"], {"integerValue": "4"})
        self.assertEqual(fields["f"], {"doubleValue": 1.5})
        self.assertEqual(fields["b"], {"booleanValue": True})
        self.assertEqual(fields["z"], {"nullValue": None})
        self.assertEqual(fields["a"]["arrayValue"]["values"][0], {"integerValue": "1"})


if __name__ == "__main__":
    unittest.main()
