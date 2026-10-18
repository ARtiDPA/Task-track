import tempfile
import unittest
from pathlib import Path
from playwright.sync_api import expect
import test_storage


class DayTaskUITests(unittest.TestCase):
    setUpClass=classmethod(test_storage.StorageTests.setUpClass.__func__)
    tearDownClass=classmethod(test_storage.StorageTests.tearDownClass.__func__)
    setUp=test_storage.StorageTests.setUp
    tearDown=test_storage.StorageTests.tearDown
    register=test_storage.StorageTests.register

    def test_planner_and_calendar_share_one_task_and_undo_completion(self):
        self.register();self.page.goto(self.url);self.page.wait_for_function('ready')
        errors=[];self.page.on('pageerror',lambda e:errors.append(str(e)))
        self.page.locator('[data-view=tasks]').click();self.page.locator('#task-new').click()
        self.page.locator('#task-title').fill('Важная встреча')
        self.page.locator('#task-day').fill('2027-01-15');self.page.locator('#task-time').fill('10:30')
        self.page.locator('#task-priority').select_option('high')
        self.page.locator('#task-dialog [type=submit]').click()
        expect(self.page.locator('#task-dialog')).not_to_be_visible()
        expect(self.page.locator('#task-list')).to_contain_text('Важная встреча')
        self.page.locator('#task-open-calendar').click()
        expect(self.page.locator('#calendar-agenda')).to_contain_text('Важная встреча')
        expect(self.page.locator('#calendar-agenda')).to_contain_text('10:30')
        self.page.locator('#calendar-agenda [data-task-toggle]').click()
        expect(self.page.locator('#calendar-task-summary')).to_have_text('План дня: 1 из 1 выполнено')
        self.page.locator('#calendar-open-planner').click()
        expect(self.page.locator('#task-done-fraction')).to_have_text('1 / 1')
        self.page.locator('#task-list [data-task-toggle]').click()
        expect(self.page.locator('#task-done-fraction')).to_have_text('0 / 1')
        self.page.reload();self.page.wait_for_function('ready')
        result=self.page.request.get(self.url+'/api/state',headers=self.api_headers).json()
        self.assertEqual(len(result['tasks']),1);self.assertFalse(result['tasks'][0]['done'])
        self.assertEqual(result['organizer']['events'],[])
        self.assertEqual(errors,[])

    def test_inbox_scheduling_reschedule_and_creation_from_calendar(self):
        self.register();self.page.goto(self.url);self.page.wait_for_function('ready')
        self.page.locator('[data-view=tasks]').click();self.page.locator('#task-new-inbox').click()
        self.page.locator('#task-title').fill('Разобрать фотографии')
        expect(self.page.locator('#task-day')).to_have_value('')
        expect(self.page.locator('#task-time')).to_be_disabled()
        self.page.locator('#task-dialog [type=submit]').click()
        expect(self.page.locator('#task-dialog')).not_to_be_visible()
        expect(self.page.locator('#task-list')).to_contain_text('Разобрать фотографии')
        self.page.locator('#task-list [data-task-edit]').first.click()
        self.page.locator('#task-day').fill('2027-01-16')
        self.page.locator('#task-dialog [type=submit]').click()
        expect(self.page.locator('#task-dialog')).not_to_be_visible()
        self.page.locator('#task-open-calendar').click()
        expect(self.page.locator('#calendar-agenda .task-row')).to_have_count(1)
        self.page.locator('#calendar-agenda [data-task-edit]').click()
        self.page.locator('#task-day').fill('2027-01-17')
        self.page.locator('#task-dialog [type=submit]').click()
        expect(self.page.locator('#task-dialog')).not_to_be_visible()
        self.assertEqual(self.page.evaluate("calendarItems().filter(e=>e.source==='task').map(e=>e.day)"),['2027-01-17'])
        self.page.locator('#calendar-add-task').click()
        expect(self.page.locator('#task-day')).to_have_value('2027-01-17')
        self.page.locator('#task-title').fill('Собрать вещи');self.page.locator('#task-dialog [type=submit]').click()
        expect(self.page.locator('#task-dialog')).not_to_be_visible()
        expect(self.page.locator('#calendar-agenda .task-row')).to_have_count(2)
        self.page.locator('#calendar-open-planner').click()
        self.page.emulate_media(reduced_motion='reduce')
        self.page.screenshot(path=str(Path(tempfile.gettempdir())/'ritmo-day-planner-desktop.png'),full_page=True)
        self.page.set_viewport_size(dict(width=390,height=844))
        self.assertTrue(self.page.evaluate('document.documentElement.scrollWidth<=innerWidth'))
        self.page.screenshot(path=str(Path(tempfile.gettempdir())/'ritmo-day-planner-mobile.png'),full_page=True)
        self.page.once('dialog',lambda d:d.accept());self.page.locator('#task-list [data-task-delete]').first.click()
        expect(self.page.locator('#task-list .task-row')).to_have_count(1)
