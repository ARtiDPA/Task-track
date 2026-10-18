import unittest
from playwright.sync_api import expect
import test_storage


class WishlistUITests(unittest.TestCase):
    setUpClass=classmethod(test_storage.StorageTests.setUpClass.__func__)
    tearDownClass=classmethod(test_storage.StorageTests.tearDownClass.__func__)
    setUp=test_storage.StorageTests.setUp
    tearDown=test_storage.StorageTests.tearDown
    register=test_storage.StorageTests.register

    def test_personal_wishlist_create_search_acquire_restore_and_reload(self):
        self.register();self.page.goto(self.url);self.page.wait_for_function('ready')
        self.page.locator('[data-view=wishlist]').click();self.page.locator('#wish-add').click()
        self.page.locator('#wish-title').fill('Новые наушники');self.page.locator('#wish-price').fill('12000,50')
        self.page.locator('#wish-category-input').fill('Техника');self.page.locator('#wish-priority').select_option('high')
        self.page.locator('#wish-dialog [type=submit]').click();expect(self.page.locator('#wish-dialog')).not_to_be_visible()
        expect(self.page.locator('#wish-count')).to_have_text('1');expect(self.page.locator('#wish-cards')).to_contain_text('12 000,50')
        self.page.locator('#wish-search').fill('Нет такого');expect(self.page.locator('.wish-card')).to_have_count(0)
        self.page.locator('#wish-search').fill('');self.page.locator('[data-wish-status][data-status=acquired]').click()
        expect(self.page.locator('#wish-acquired')).to_have_text('1');self.page.locator('#wish-status').select_option('acquired')
        expect(self.page.locator('#wish-cards')).to_contain_text('Сбылось')
        self.page.locator('[data-wish-status][data-status=wanted]').click()
        self.page.reload();self.page.wait_for_function('ready');self.page.locator('[data-view=wishlist]').click()
        expect(self.page.locator('#wish-cards')).to_contain_text('Новые наушники')
        self.page.set_viewport_size(dict(width=390,height=844));self.assertTrue(self.page.evaluate('document.documentElement.scrollWidth<=innerWidth'))
