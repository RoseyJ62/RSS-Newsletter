from datetime import datetime
import unittest
from datetime import UTC

from news_digest.models import ScheduleSettings
from news_digest.scheduler import compute_next_run


class SchedulerTests(unittest.TestCase):
    def test_daily_schedule_moves_to_tomorrow_after_time_passed(self):
        settings = ScheduleSettings(frequency="daily", time="07:30", timezone="UTC")
        now = datetime(2026, 4, 20, 8, 0, tzinfo=UTC)

        next_run = compute_next_run(settings, now)

        self.assertEqual(next_run.day, 21)
        self.assertEqual(next_run.hour, 7)
        self.assertEqual(next_run.minute, 30)


    def test_weekly_schedule_selects_configured_day(self):
        settings = ScheduleSettings(frequency="weekly", day="friday", time="7:30", timezone="UTC")
        now = datetime(2026, 4, 20, 8, 0, tzinfo=UTC)

        next_run = compute_next_run(settings, now)

        self.assertEqual(next_run.weekday(), 4)
        self.assertEqual(next_run.day, 24)


if __name__ == "__main__":
    unittest.main()
