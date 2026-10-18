import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from playwright.sync_api import expect
import test_storage


class FocusUITests(unittest.TestCase):
    setUpClass=classmethod(test_storage.StorageTests.setUpClass.__func__)
    tearDownClass=classmethod(test_storage.StorageTests.tearDownClass.__func__)
    setUp=test_storage.StorageTests.setUp
    tearDown=test_storage.StorageTests.tearDown
    register=test_storage.StorageTests.register

    def test_timer_pause_reload_finish_graphs_and_settings(self):
        import time
        base=int(time.time()*1000)
        self.register();self.page.goto(self.url);self.page.wait_for_function('ready')
        errors=[];self.page.on('pageerror',lambda e:errors.append(str(e)))
        self.page.locator('[data-view=focus]').click();self.page.locator('#focus-settings-open').click()
        self.page.locator('#focus-auto-pause').uncheck();self.page.locator('#focus-goal').fill('60')
        self.page.locator('#focus-settings-dialog [type=submit]').click();expect(self.page.locator('#focus-settings-dialog')).not_to_be_visible()
        with patch('focus.now_ms',return_value=base):
            self.page.locator('#focus-title').fill('Глубокая работа');self.page.locator('#focus-minutes').fill('25');self.page.locator('#focus-start').click()
            expect(self.page.locator('#focus-pause')).to_be_visible()
        with patch('focus.now_ms',return_value=base+600000):
            self.page.locator('#focus-pause').click();expect(self.page.locator('#focus-resume')).to_be_visible()
            expect(self.page.locator('#focus-clock')).to_have_text('15:00')
            self.page.reload();self.page.wait_for_function('ready');self.page.locator('[data-view=focus]').click()
            expect(self.page.locator('#focus-clock')).to_have_text('15:00');self.page.locator('#focus-resume').click()
            expect(self.page.locator('#focus-pause')).to_be_visible()
        with patch('focus.now_ms',return_value=base+900000):
            self.page.locator('#focus-finish').click();expect(self.page.locator('#focus-start')).to_be_visible()
            expect(self.page.locator('#focus-history')).to_contain_text('Глубокая работа')
            expect(self.page.locator('#focus-all-time')).to_have_text('15 мин')
            self.page.locator('[data-focus-period="30"]').click();expect(self.page.locator('.focus-bar-column')).to_have_count(30)
            self.assertTrue(self.page.locator('#focus-chart i').evaluate_all("bars=>bars.some(b=>parseFloat(b.style.height)>0)"))
            self.page.emulate_media(reduced_motion='reduce')
            self.page.evaluate('scrollTo(0,0)')
            self.page.screenshot(path=str(Path(tempfile.gettempdir())/'ritmo-focus-desktop.png'),full_page=True)
            self.page.set_viewport_size(dict(width=390,height=844));self.assertTrue(self.page.evaluate('document.documentElement.scrollWidth<=innerWidth'))
            self.page.evaluate('scrollTo(0,0)')
            self.page.screenshot(path=str(Path(tempfile.gettempdir())/'ritmo-focus-mobile.png'),full_page=True)
        self.assertEqual(errors,[])

    def test_auto_pause_and_profile_privacy(self):
        self.register();self.page.goto(self.url);self.page.wait_for_function('ready');self.page.locator('[data-view=focus]').click()
        self.page.locator('#focus-start').click();expect(self.page.locator('#focus-pause')).to_be_visible()
        self.page.evaluate("window.dispatchEvent(new Event('blur'))")
        expect(self.page.locator('#focus-resume')).to_be_visible();expect(self.page.locator('#focus-distractions')).to_have_text('1')
        self.page.request.post(self.url+'/api/auth/register',data=dict(email='other@example.com',name='Other',password='other-password'))
        self.page.reload();self.page.wait_for_function('ready');self.page.locator('[data-view=focus]').click()
        expect(self.page.locator('#focus-start')).to_be_visible();expect(self.page.locator('#focus-all-time')).to_have_text('0 сек')
