"""Theme controls, motion preferences and asset integrity in an isolated profile."""
from playwright.sync_api import sync_playwright, expect
from test_server import ServerFixture


class ThemeTests(ServerFixture):
    def test_effects_persist_and_all_views_fit_mobile(self):
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            context = browser.new_context(viewport={'width': 390, 'height': 844})
            context.add_cookies([dict(name='ritmo_refresh', value=self.cookie.split('=', 1)[1],
                                     url=self.url + '/api/auth', httpOnly=True, sameSite='Strict')])
            page = context.new_page()
            errors = []
            page.on('pageerror', lambda error: errors.append(str(error)))
            page.goto(self.url)
            expect(page.locator('.auth-screen')).not_to_be_visible()
            expect(page.locator('#matrix-rain')).to_have_attribute('aria-hidden', 'true')
            toggle = page.locator('.topbar .effects-toggle')
            toggle.click()
            expect(toggle).to_have_attribute('aria-pressed', 'false')
            page.reload()
            expect(toggle).to_have_attribute('aria-pressed', 'false')
            for view in ['dashboard', 'habits', 'analytics', 'finance', 'focus', 'tasks',
                         'calendar', 'wishlist', 'relationships', 'water', 'achievements']:
                page.locator(f'[data-view="{view}"]').click()
                self.assertTrue(page.evaluate('document.documentElement.scrollWidth <= innerWidth'), view)
            self.assertEqual(errors, [])
            context.close()
            browser.close()

    def test_reduced_motion_disables_effects_on_login(self):
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            page = browser.new_page(reduced_motion='reduce')
            page.goto(self.url)
            expect(page.locator('.auth-screen')).to_be_visible()
            expect(page.locator('html')).to_have_class('effects-off')
            self.assertEqual(page.locator('#matrix-rain').evaluate('e => getComputedStyle(e).display'), 'none')
            expect(page.locator('.auth-effects')).to_be_visible()
            browser.close()
