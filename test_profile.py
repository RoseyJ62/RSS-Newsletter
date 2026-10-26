import json
import os
import tempfile
import unittest
from unittest import mock

import profile


class RatingTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        patcher = mock.patch.object(profile, "PROFILE_PATH", os.path.join(self.tmp.name, "user_profile.json"))
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_five_point_adjustments_match_original_formula(self):
        for rating in range(1, 6):
            self.assertAlmostEqual(profile.rating_adjustment(rating, 5), (rating - 3) * 0.1)

    def test_rating_adjusts_matched_keywords_and_logs_history(self):
        profile.update_weights(["AI", "digital"], 5, scale=5)

        data = profile.load_profile()
        self.assertAlmostEqual(data["keyword_weights"]["ai"], 1.2)
        self.assertAlmostEqual(data["keyword_weights"]["digital"], 1.2)
        self.assertEqual(data["history"][-1]["rating"], 5)
        self.assertEqual(data["history"][-1]["scale"], 5)

    def test_weights_never_drop_below_floor(self):
        for _ in range(20):
            profile.update_weights(["ai"], 1, scale=5)
        self.assertAlmostEqual(profile.load_profile()["keyword_weights"]["ai"], 0.1)

    def test_four_point_scale_has_no_neutral_and_matches_old_strengths(self):
        self.assertEqual(profile.CURRENT_RATING_SCALE, 4)
        self.assertEqual([profile.rating_adjustment(r, 4) for r in range(1, 5)], [-0.2, -0.1, 0.1, 0.2])
        self.assertTrue(all(profile.rating_adjustment(r, 4) != 0 for r in range(1, 5)))

    def test_default_rating_uses_four_point_scale_and_tags_history(self):
        profile.update_weights(["ai"], 3)

        data = profile.load_profile()
        self.assertAlmostEqual(data["keyword_weights"]["ai"], 1.1)
        self.assertEqual(data["history"][-1]["scale"], 4)
        self.assertEqual(data["history"][-1]["label"], "Like")

    def test_legacy_history_is_kept_and_read_as_five_point(self):
        legacy = {"keyword_weights": {"ai": 1.8}, "history": [{"keywords": ["ai"], "rating": 3, "adjustment": 0.0}]}
        with open(profile.PROFILE_PATH, "w", encoding="utf-8") as f:
            json.dump(legacy, f)

        profile.update_weights(["ai"], 3)

        data = profile.load_profile()
        self.assertEqual(data["history"][0], legacy["history"][0])
        self.assertEqual(profile.history_entry_scale(data["history"][0]), 5)
        self.assertEqual(profile.history_entry_scale(data["history"][1]), 4)
        # Existing weight is kept and only the new rating's adjustment is applied.
        self.assertAlmostEqual(data["keyword_weights"]["ai"], 1.9)

    def test_mixed_case_weight_keys_are_folded_to_lowercase(self):
        with open(profile.PROFILE_PATH, "w", encoding="utf-8") as f:
            json.dump({"keyword_weights": {"AI": 1.0, "ai": 1.8, "OSF HealthCare": 2.0}, "history": []}, f)

        weights = profile.load_profile()["keyword_weights"]
        self.assertEqual(weights, {"ai": 1.8, "osf healthcare": 2.0})

    def test_rating_without_keywords_changes_no_weights(self):
        profile.update_weights([], 5, scale=5)
        data = profile.load_profile()
        self.assertEqual(data["keyword_weights"], {})
        self.assertEqual(len(data["history"]), 1)


if __name__ == "__main__":
    unittest.main()
