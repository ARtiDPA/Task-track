"""Browser-to-database migration, persistence, and connection recovery."""
import json
import tempfile
import threading
import unittest
from pathlib import Path
from playwright.sync_api import sync_playwright, expect
from test_server import QuietHandler, Store, ThreadingHTTPServer
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

    def seed_legacy(self):
        legacy = {'habits': [{'id': 'legacy', 'name': 'Старая привычка', 'category': 'Развитие',
                             'emoji': '📖', 'color': '#9772db', 'logs': [today()]}]}
        self.context.add_init_script("localStorage.setItem('ritmo-v1',"+json.dumps(json.dumps(legacy))+');')

    def test_legacy_progress_is_imported_and_survives_browser_cache_removal(self):
        self.seed_legacy()
        self.page.goto(self.url)
        expect(self.page.locator('#connection-panel')).not_to_be_visible()
        expect(self.page.locator('.habit-row')).to_have_count(1)
        expect(self.page.locator('#period-percent')).to_have_text('100')
        data = self.page.request.get(self.url+'/api/state').json()
        self.assertEqual(data['habits'][0]['logs'], [today()])
        self.assertEqual(data['habits'][0]['createdAt'], today())
        # A new browser with localStorage entirely disabled still loads the database.
        other = self.browser.new_context(timezone_id='Europe/Moscow')
        other.add_init_script("Storage.prototype.getItem=()=>{throw new Error('blocked')};Storage.prototype.setItem=()=>{throw new Error('blocked')};")
        page = other.new_page()
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
        data=self.page.request.get(self.url+'/api/state').json()
        self.assertEqual(data['habits'][-1]['emoji'], '🎹')
        self.page.set_viewport_size({'width':390,'height':700})
        self.page.locator('#add-habit').click()
        self.page.locator('#emoji-search').fill('несуществующий значок')
        expect(self.page.locator('.emoji-empty')).to_be_visible()
        self.page.locator('#emoji-search').fill('')
        expect(self.page.locator('.emoji-option')).to_have_count(72)
        self.page.locator('#habit-dialog').screenshot(path=str(Path(tempfile.gettempdir())/'ritmo-icons.png'))


if __name__ == '__main__':
    unittest.main()
