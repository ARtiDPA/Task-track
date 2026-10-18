"""Check the actual JavaScript metric functions in a browser."""
import unittest
from pathlib import Path
from playwright.sync_api import sync_playwright


class MetricTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.playwright = sync_playwright().start()
        cls.browser = cls.playwright.chromium.launch(channel='msedge', headless=True)
        cls.page = cls.browser.new_page()
        cls.page.add_script_tag(path=str(Path(__file__).resolve().parents[1] / 'metrics.js'))

    @classmethod
    def tearDownClass(cls):
        cls.browser.close()
        cls.playwright.stop()

    def rate(self, habits, days):
        return self.page.evaluate('([habits,days])=>RitmoMetrics.rate(habits,days)', [habits, days])

    def test_first_day_completed_is_100_percent_even_late_in_month(self):
        habit = {'createdAt': '2026-10-18', 'logs': ['2026-10-18']}
        self.assertEqual(self.rate([habit], [f'2026-10-{i:02}' for i in range(1, 19)]), 100)

    def test_each_habit_has_its_own_denominator(self):
        habits = [{'createdAt': '2026-10-17', 'logs': ['2026-10-17', '2026-10-18']},
                  {'createdAt': '2026-10-18', 'logs': ['2026-10-18']}]
        self.assertEqual(self.rate(habits, ['2026-10-17', '2026-10-18']), 100)
        habits[1]['logs'] = []
        self.assertEqual(self.rate(habits, ['2026-10-17', '2026-10-18']), 67)
        self.assertEqual(self.rate(habits, ['2026-10-17']), 100)

    def test_missing_days_count_after_creation_and_period_is_respected(self):
        habit = {'createdAt': '2026-10-01', 'logs': ['2026-10-01', '2026-10-18']}
        self.assertEqual(self.rate([habit], ['2026-10-17', '2026-10-18']), 50)
        self.assertEqual(self.rate([habit], []), 0)
        self.assertEqual(self.rate([], ['2026-10-18']), 0)

    def test_migration_uses_oldest_mark_and_preserves_recorded_creation(self):
        result = self.page.evaluate("""() => [
            RitmoMetrics.creationDate({logs:['2026-10-15','2026-10-12']},'2026-10-18'),
            RitmoMetrics.creationDate({logs:[]},'2026-10-18'),
            RitmoMetrics.creationDate({createdAt:'2026-10-01',logs:['2026-10-12']},'2026-10-18'),
            RitmoMetrics.creationDate({createdAt:'2026-02-31',logs:[]},'2026-10-18')
        ]""")
        self.assertEqual(result, ['2026-10-12','2026-10-18','2026-10-01','2026-10-18'])


if __name__ == '__main__':
    unittest.main()
