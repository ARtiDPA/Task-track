import unittest
from pathlib import Path
from playwright.sync_api import sync_playwright


class FocusMathTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.playwright=sync_playwright().start();cls.browser=cls.playwright.chromium.launch(headless=True)
        cls.page=cls.browser.new_page();cls.page.add_script_tag(path=str(Path(__file__).resolve().parents[1] / 'frontend' / 'static' / 'js' / 'focus-math.js'))

    @classmethod
    def tearDownClass(cls):cls.browser.close();cls.playwright.stop()

    def test_daily_graph_goal_streak_and_missing_days(self):
        data=dict(settings=dict(goalMinutes=30),daily=[dict(day='2026-10-17',milliseconds=60000),dict(day='2026-10-18',milliseconds=120000),dict(day='2026-10-19',milliseconds=2400000)])
        result=self.page.evaluate("d=>RitmoFocus.summary(d,'2026-10-19',7)",data)
        self.assertEqual(result['streak'],3);self.assertEqual(result['goalPercent'],100)
        self.assertEqual(result['periodMs'],2580000);self.assertEqual(len(result['series']),7)
        self.assertEqual(result['activeDays'],3)
        self.assertEqual(result['series'][0]['milliseconds'],0)

    def test_yesterday_streak_and_old_sessions_excluded_from_period(self):
        data=dict(daily=[dict(day='2026-01-01',milliseconds=999999),dict(day='2026-10-18',milliseconds=60000)])
        result=self.page.evaluate("d=>RitmoFocus.summary(d,'2026-10-19',30)",data)
        self.assertEqual(result['streak'],1);self.assertEqual(result['periodMs'],60000)
        self.assertEqual(result['todayMs'],0);self.assertEqual(result['goalPercent'],0)
