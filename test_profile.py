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

    def test_rating_without_keywords_changes_no_weights(self):
        profile.update_weights([], 5, scale=5)
        data = profile.load_profile()
        self.assertEqual(data["keyword_weights"], {})
        self.assertEqual(len(data["history"]), 1)


if __name__ == "__main__":
    unittest.main()
