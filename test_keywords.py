import json
import os
import tempfile
import unittest
from unittest import mock

import keywords
import scorer


class KeywordTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = os.path.join(self.tmp.name, "osf_context.json")
        self.context = {
            "focus_areas": [{"name": "Innovation", "weight": 2, "keywords": ["AI", "digital"]}],
            "keyword_rules": {
                "high_signal": ["acquisition", "OSF HealthCare"],
                "low_signal": ["update"],
                "low_signal_requires_pair": True,
            },
        }
        with open(self.path, "w", encoding="utf-8") as f:
            json.dump(self.context, f)
        patcher = mock.patch.object(scorer, "_context_path", lambda: self.path)
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_load_returns_existing_keywords(self):
        self.assertEqual(keywords.load_high_signal(), ["acquisition", "OSF HealthCare"])

    def test_save_replaces_only_high_signal(self):
        keywords.save_high_signal(["acquisition", "merger"])

        with open(self.path, encoding="utf-8") as f:
            saved = json.load(f)
        self.assertEqual(saved["keyword_rules"]["high_signal"], ["acquisition", "merger"])
        self.assertEqual(saved["keyword_rules"]["low_signal"], ["update"])
        self.assertEqual(saved["focus_areas"], self.context["focus_areas"])

    def test_save_creates_rules_when_missing(self):
        with open(self.path, "w", encoding="utf-8") as f:
            json.dump({"focus_areas": []}, f)

        keywords.save_high_signal(["merger"])
        self.assertEqual(keywords.load_high_signal(), ["merger"])

    def test_duplicates_ignore_case_and_spacing(self):
        existing = ["acquisition", "OSF HealthCare"]
        self.assertEqual(keywords.find_duplicate("  osf   healthcare ", existing), "OSF HealthCare")
        self.assertIsNone(keywords.find_duplicate("merger", existing))
        # Editing an entry to a new casing of itself is not a duplicate.
        self.assertIsNone(keywords.find_duplicate("OSF Healthcare", existing, ignore_index=1))

    def test_clean_trims_and_collapses_spaces(self):
        self.assertEqual(keywords.clean("  patient   care "), "patient care")

    def test_saved_high_signal_keyword_affects_scoring(self):
        # A low-signal word only counts when a high-signal keyword is also present.
        context = {
            "focus_areas": [{"name": "News", "weight": 1, "keywords": ["update", "merger"]}],
            "keyword_rules": {"high_signal": [], "low_signal": ["update"], "low_signal_requires_pair": True},
        }
        with open(self.path, "w", encoding="utf-8") as f:
            json.dump(context, f)
        profile = {"keyword_weights": {}}

        before = scorer.score_article("Merger update", "", profile)
        keywords.save_high_signal(["merger"])
        after = scorer.score_article("Merger update", "", profile)

        self.assertEqual(sorted(before["matched_keywords"]), ["merger"])
        self.assertEqual(sorted(after["matched_keywords"]), ["merger", "update"])


if __name__ == "__main__":
    unittest.main()
