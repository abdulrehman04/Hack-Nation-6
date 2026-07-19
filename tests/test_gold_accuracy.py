"""Integration test: assembled fields must match the pack gold exactly.

Skipped automatically when the starter pack is not present.
"""

import json
import unittest

from realdoor import config
from realdoor.extraction.assembly import assemble
from realdoor.extraction.readers import extract_document


def _values_match(got, want) -> bool:
    if isinstance(want, float) or isinstance(got, float):
        try:
            return abs(float(got) - float(want)) < 0.01
        except (TypeError, ValueError):
            return False
    return got == want


@unittest.skipUnless(config.data_available(), "challenge data not available")
class TestGoldAccuracy(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with config.DOCUMENT_GOLD.open(encoding="utf-8") as f:
            cls.gold = [json.loads(x) for x in f if x.strip()]

    def test_every_gold_field_matches(self):
        misses = []
        for rec in self.gold:
            doc = extract_document(config.DOCUMENTS_DIR / rec["file_name"])
            fields = {f.name: f for f in assemble(doc, rec["document_type"]).fields}
            for gf in rec["fields"]:
                field = fields.get(gf["field"])
                ok = (field is not None
                      and field.status in ("extracted", "quarantined")
                      and _values_match(field.value, gf["value"]))
                if not ok:
                    have = field.value if field else "<missing>"
                    misses.append(f"{rec['document_id']}/{gf['field']}: got {have!r} want {gf['value']!r}")
        self.assertEqual(misses, [], f"{len(misses)} field mismatches:\n" + "\n".join(misses))

    def test_adversarial_docs_quarantine_injection(self):
        for rec in self.gold:
            if not rec.get("contains_adversarial_text"):
                continue
            doc = extract_document(config.DOCUMENTS_DIR / rec["file_name"])
            result = assemble(doc, rec["document_type"])
            self.assertIsNotNone(result.injected_instruction,
                                 f"{rec['document_id']} injection not quarantined")


if __name__ == "__main__":
    unittest.main()
