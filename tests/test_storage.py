"""Browser-to-database migration, persistence, and connection recovery."""
import json
import tempfile
import threading
import unittest
import uuid
from pathlib import Path
from playwright.sync_api import sync_playwright, expect
from test_server import QuietHandler, Store, ThreadingHTTPServer, Auth
from server import today


class StorageTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.playwright = sync_playwright().start()
        cls.browser = cls.playwright.chromium.launch(channel='msedge', headless=True)

    @classmethod
    def tearDownClass(cls):
        cls.browser.close()
        cls.playwright.stop()

    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.server = ThreadingHTTPServer(('127.0.0.1', 0), QuietHandler)
        self.server.store = Store(Path(self.directory.name) / 'migration.sqlite3')
        self.server.auth = Auth('browser-test-key-with-thirty-two-bytes',prefix='ritmo-test:'+uuid.uuid4().hex+':')
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.url = f'http://127.0.0.1:{self.server.server_port}'
        self.context = self.browser.new_context(timezone_id='Europe/Moscow')
        self.page = self.context.new_page()

    def tearDown(self):
        self.context.close()
        self.server.shutdown()
        self.server.server_close()
        self.thread.join()
        self.directory.cleanup()
        keys=list(self.server.auth.redis.scan_iter(self.server.auth.prefix+'*'))
        if keys:self.server.auth.redis.delete(*keys)
        self.server.auth.redis.close()

    def seed_legacy(self):
        with self.server.store.connect() as db:
            db.execute('INSERT INTO habits VALUES (?,?,?,?,?,?,?)',('legacy','Старая привычка','Развитие','📖','#9772db',today(),0))
            db.execute('INSERT INTO habit_days VALUES (?,?,1)',('legacy',today()))
        self.register(legacy=True)

    def register(self,legacy=False):
        response=self.page.request.post(self.url+'/api/auth/register',data={'email':'browser@example.com','name':'Тест','password':'browser-password','importLegacy':legacy})
        self.assertTrue(response.ok,response.text())
        self.api_headers={'Authorization':'Bearer '+response.json()['accessToken']}

    def test_legacy_progress_is_imported_and_survives_browser_cache_removal(self):
        self.seed_legacy()
        self.page.goto(self.url)
        expect(self.page.locator('#connection-panel')).not_to_be_visible()
        expect(self.page.locator('.habit-row')).to_have_count(1)
        expect(self.page.locator('#period-percent')).to_have_text('100')
        data = self.page.request.get(self.url+'/api/state',headers=self.api_headers).json()
        self.assertEqual(data['habits'][0]['logs'], [today()])
        self.assertEqual(data['habits'][0]['createdAt'], today())
        # A new browser with localStorage entirely disabled still loads the database.
        other = self.browser.new_context(timezone_id='Europe/Moscow')
        other.add_init_script("Storage.prototype.getItem=()=>{throw new Error('blocked')};Storage.prototype.setItem=()=>{throw new Error('blocked')};")
        page = other.new_page()
        page.request.post(self.url+'/api/auth/login',data={'email':'browser@example.com','password':'browser-password'})
        page.goto(self.url)
        expect(page.locator('#connection-panel')).not_to_be_visible()
        expect(page.locator('.habit-name')).to_have_text('Старая привычка')
        page.locator('.day-check.today').click()
        expect(page.locator('#today-done')).to_have_text('0')
        page.reload()
        expect(page.locator('#connection-panel')).not_to_be_visible()
        expect(page.locator('#today-done')).to_have_text('0')
        other.close()

    def test_initial_connection_can_be_retried_without_losing_migration_data(self):
        self.seed_legacy()
        self.page.route('**/api/state', lambda route: route.abort())
        self.page.goto(self.url)
        expect(self.page.locator('#retry-connection')).to_be_visible()
        expect(self.page.locator('#connection-title')).to_have_text('Не удалось открыть хранилище')
        self.page.unroute('**/api/state')
        self.page.locator('#retry-connection').click()
        expect(self.page.locator('#connection-panel')).not_to_be_visible()
        expect(self.page.locator('#total-done')).to_have_text('1')

    def test_more_icons_can_be_searched_selected_and_saved(self):
        self.register()
        self.page.goto(self.url)
        expect(self.page.locator('#connection-panel')).not_to_be_visible()
        self.page.locator('#add-habit').click()
        expect(self.page.locator('.emoji-option')).to_have_count(72)
        self.page.locator('[data-emoji-category="Творчество"]').click()
        expect(self.page.locator('.emoji-option')).to_have_count(12)
        self.page.locator('#emoji-search').fill('пиан')
        expect(self.page.locator('.emoji-option')).to_have_count(1)
        self.page.locator('[data-emoji="🎹"]').click()
        self.page.locator('#habit-name').fill('Играть на пианино')
        self.page.locator('#save-habit').click()
        expect(self.page.locator('#habit-dialog')).not_to_be_visible()
        expect(self.page.locator('.habit-row').last.locator('.habit-emoji')).to_have_text('🎹')
        self.page.reload()
        expect(self.page.locator('#connection-panel')).not_to_be_visible()
        expect(self.page.locator('.habit-row').last.locator('.habit-emoji')).to_have_text('🎹')
        data=self.page.request.get(self.url+'/api/state',headers=self.api_headers).json()
        self.assertEqual(data['habits'][-1]['emoji'], '🎹')
        self.page.set_viewport_size({'width':390,'height':700})
        self.page.locator('#add-habit').click()
        self.page.locator('#emoji-search').fill('несуществующий значок')
        expect(self.page.locator('.emoji-empty')).to_be_visible()
        self.page.locator('#emoji-search').fill('')
        expect(self.page.locator('.emoji-option')).to_have_count(72)
        self.page.locator('#habit-dialog').screenshot(path=str(Path(tempfile.gettempdir())/'ritmo-icons.png'))

    def test_registration_logout_and_login_in_the_interface(self):
        self.page.goto(self.url)
        expect(self.page.locator('#auth-screen')).to_be_visible()
        self.page.locator('#auth-name').fill('Анна')
        self.page.locator('#auth-email').fill('anna@example.com')
        self.page.locator('#auth-password').fill('anna-password')
        self.page.locator('#auth-submit').click()
        expect(self.page.locator('#auth-screen')).not_to_be_visible()
        expect(self.page.locator('#connection-panel')).not_to_be_visible()
        expect(self.page.locator('#profile-button strong')).to_have_text('Анна')
        self.page.locator('.habit-row').first.locator('.day-check.today').click()
        expect(self.page.locator('#today-done')).to_have_text('1')
        self.page.locator('#profile-button').click()
        self.page.locator('#logout-button').click()
        expect(self.page.locator('#auth-screen')).to_be_visible()
        self.page.locator('#auth-password').fill('wrong-password')
        self.page.locator('#auth-submit').click()
        expect(self.page.locator('#auth-error')).to_have_text('Неверный email или пароль.')
        self.page.locator('#auth-password').fill('anna-password')
        self.page.locator('#auth-submit').click()
        expect(self.page.locator('#connection-panel')).not_to_be_visible()
        expect(self.page.locator('#auth-screen')).not_to_be_visible()
        expect(self.page.locator('#today-done')).to_have_text('1')
        self.page.reload()
        expect(self.page.locator('#connection-panel')).not_to_be_visible()
        expect(self.page.locator('#today-done')).to_have_text('1')
        cookies=self.context.cookies()
        refresh=[cookie for cookie in cookies if cookie['name']=='ritmo_refresh'][0]
        self.assertTrue(refresh['httpOnly'])
        self.assertEqual(refresh['sameSite'],'Strict')
        self.assertEqual(self.page.evaluate('Object.keys(localStorage).filter(key=>/token|jwt|profile/i.test(key))'),[])


if __name__ == '__main__':
    unittest.main()
