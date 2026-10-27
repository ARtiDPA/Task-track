import unittest
from pathlib import Path
from playwright.sync_api import sync_playwright


class AchievementTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.playwright=sync_playwright().start()
        cls.browser=cls.playwright.chromium.launch(channel='msedge',headless=True)
        cls.page=cls.browser.new_page()
        cls.page.add_script_tag(path=str(Path(__file__).resolve().parents[1] / 'frontend' / 'static' / 'js' / 'achievements.js'))

    @classmethod
    def tearDownClass(cls):
        cls.browser.close();cls.playwright.stop()

    def evaluate(self,habits):
        return {item['id']:item for item in self.page.evaluate('habits=>RitmoAchievements.evaluate(habits)',habits)}

    def test_empty_profile_has_no_fake_achievements(self):
        items=self.evaluate([])
        self.assertEqual(len(items),28)
        self.assertTrue(all(not item['unlocked'] for item in items.values()))

    def test_streaks_and_progress_are_real(self):
        items=self.evaluate([{'createdAt':'2026-10-01','category':'Reading','logs':['2026-10-01','2026-10-02','2026-10-03']}])
        self.assertTrue(items['first']['unlocked'])
        self.assertTrue(items['streak-3']['unlocked'])
        self.assertFalse(items['streak-7']['unlocked'])
        self.assertEqual(items['streak-7']['value'],3)
        self.assertEqual(items['streak-7']['percent'],43)
        self.assertTrue(items['perfect-1']['unlocked'])

    def test_new_habit_does_not_erase_previous_perfect_days(self):
        items=self.evaluate([{'createdAt':'2026-10-01','category':'Reading','logs':['2026-10-01']},
                             {'createdAt':'2026-10-02','category':'Sport','logs':[]}])
        self.assertTrue(items['perfect-1']['unlocked'])
        self.assertEqual(items['perfect-1']['value'],1)


if __name__=='__main__':unittest.main()
