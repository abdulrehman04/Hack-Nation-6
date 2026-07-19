"""Tests for the Discover property loader and its compliance guarantees."""

import unittest

from realdoor.discover import load_properties


class TestDiscover(unittest.TestCase):
    def setUp(self):
        self.properties = load_properties()

    def test_returns_full_frozen_subset(self):
        self.assertEqual(len(self.properties), 32)

    def test_neutral_alphabetical_order(self):
        names = [p["project_name"] for p in self.properties]
        self.assertEqual(names, sorted(names))

    def test_availability_always_unknown(self):
        # The dataset has no availability data; we must never imply a unit is open.
        self.assertTrue(all(p["availability"] == "unknown" for p in self.properties))

    def test_no_ranking_or_score_fields(self):
        banned = {"score", "rank", "match", "recommended", "acceptance", "rent"}
        for prop in self.properties:
            self.assertFalse(banned & set(prop.keys()))

    def test_every_property_carries_provenance(self):
        for prop in self.properties:
            self.assertTrue(prop["source_url"])
            self.assertTrue(prop["retrieved_utc"])

    def test_bedroom_counts_are_ints(self):
        beds = self.properties[0]["bedrooms"]
        self.assertEqual(set(beds), {"studio", "one", "two", "three", "four"})
        self.assertTrue(all(isinstance(v, int) for v in beds.values()))


if __name__ == "__main__":
    unittest.main()
