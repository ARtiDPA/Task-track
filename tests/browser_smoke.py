"""Run: python -m pip install playwright; python tests/browser_smoke.py

Creates an isolated temporary database and server; never modifies real user data.
Uses installed Microsoft Edge; no browser download required on Windows.
"""
import json
import tempfile
import threading
from pathlib import Path
from playwright.sync_api import sync_playwright, expect
from test_server import QuietHandler, Store, ThreadingHTTPServer


def run_checks(url):
    with sync_playwright() as p:
        browser = p.chromium.launch(channel="msedge", headless=True)
        context = browser.new_context(viewport={"width": 1440, "height": 1000}, timezone_id="Europe/Moscow")
        page = context.new_page()
        errors = []
        page.on("pageerror", lambda error: errors.append(str(error)))
        page.goto(url)
        expect(page.locator('#connection-panel')).not_to_be_visible()
        expect(page.locator(".habit-row")).to_have_count(6)
        expect(page.locator("#total-done")).to_have_text("0")
        assert page.locator(".heat-cell:not(.blank)").count() == 365

        # Add a real habit and customize its appearance.
        page.locator("#add-habit").click()
        page.locator("#habit-name").fill("Утренняя зарядка")
        page.locator("#habit-category").select_option("Спорт")
        page.locator('[data-emoji="💪"]').click()
        page.locator('[data-color="#6aaa91"]').click()
        page.locator("#save-habit").click()
        expect(page.locator(".habit-row")).to_have_count(7)
        row = page.locator(".habit-row").last
        expect(row.locator(".habit-name")).to_have_text("Утренняя зарядка")
        row.locator(".day-check.today").click()
        expect(page.locator("#today-done")).to_have_text("1")
        expect(page.locator("#total-done")).to_have_text("1")
        expect(page.locator("#best-streak")).to_have_text("1")
        page.reload()
        expect(page.locator(".habit-row")).to_have_count(7)
        expect(page.locator(".habit-row").last.locator(".day-check.today")).to_have_attribute("aria-pressed", "true")

        # A new browser context gets its progress from SQLite, without a local cache.
        second = browser.new_context(timezone_id='Europe/Moscow')
        other = second.new_page()
        other.goto(url)
        expect(other.locator('#connection-panel')).not_to_be_visible()
        expect(other.locator('#total-done')).to_have_text('1')
        second.close()

        # Failed saves do not change the UI or claim success; retry works.
        page.route('**/api/habits/*/days/*', lambda route: route.abort())
        page.locator('.habit-row').last.locator('.day-check.today').click()
        expect(page.locator('.live-label')).to_have_text('Не сохранено')
        expect(page.locator('#total-done')).to_have_text('1')
        expect(page.locator('.habit-row').last.locator('.day-check.today')).to_have_attribute('aria-pressed', 'true')
        page.unroute('**/api/habits/*/days/*')

        # Edit preserves history; activity filtering and period switches work.
        row = page.locator(".habit-row").last
        row.hover()
        row.locator(".habit-edit").click()
        page.locator("#habit-name").fill("Зарядка 15 минут")
        page.locator("#save-habit").click()
        expect(page.locator(".habit-row").last.locator(".habit-name")).to_have_text("Зарядка 15 минут")
        expect(page.locator("#total-done")).to_have_text("1")
        habit_id = page.locator(".habit-row").last.locator(".day-check").first.get_attribute("data-habit")
        page.locator("#activity-habit").select_option(habit_id)
        expect(page.locator("#year-total")).to_have_text("1 выполнение")
        assert page.locator('.heat-cell[data-level="4"]').count() == 1
        page.locator('[data-period="month"]').click()
        assert page.locator(".chart-svg circle").count() >= 1
        page.locator('[data-view="achievements"]').click()
        expect(page.locator("#achievements-view")).to_be_visible()
        expect(page.locator(".achievement:not(.locked)")).to_have_count(1)
        page.locator('[data-view="analytics"]').click()
        expect(page.locator(".chart-card")).to_be_visible()
        expect(page.locator(".habits-card")).not_to_be_visible()
        page.locator('[data-view="habits"]').click()
        expect(page.locator(".habits-card")).to_be_visible()
        expect(page.locator(".chart-card")).not_to_be_visible()

        # Deletion is explicit and reversible until confirmed.
        row = page.locator(".habit-row").last
        row.hover()
        row.locator(".habit-edit").click()
        page.once("dialog", lambda dialog: dialog.dismiss())
        page.locator(".delete-habit").click()
        expect(page.locator(".habit-row")).to_have_count(7)
        page.once("dialog", lambda dialog: dialog.accept())
        page.locator(".delete-habit").click()
        expect(page.locator(".habit-row")).to_have_count(6)
        expect(page.locator("#total-done")).to_have_text("0")

        # Completing the whole day unlocks the right achievement.
        page.locator('[data-view="dashboard"]').click()
        for index in range(6):
            page.locator(".habit-row").nth(index).locator(".day-check.today").click()
        expect(page.locator("#today-percent")).to_have_text("100% от цели")
        expect(page.locator(".achievement:not(.locked)")).to_have_count(2)
        assert page.locator(".confetti").count() > 0
        page.locator(".habit-row").first.locator(".day-check.today").click()
        expect(page.locator("#today-done")).to_have_text("5")

        # No page-level horizontal scroll, including compact phones.
        layouts = {}
        for width in [1440, 1280, 1024, 900, 768, 600, 520, 430, 390, 375, 360]:
            page.set_viewport_size({"width": width, "height": 1000})
            page.wait_for_timeout(150)
            overflow = page.evaluate("document.documentElement.scrollWidth > innerWidth")
            layouts[width] = not overflow
            assert not overflow, f"Horizontal overflow at {width}px"
            # Summary and chart must follow the heading, without negative-margin overlap.
            heading = page.locator('.chart-card .section-header').bounding_box()
            summary = page.locator('.chart-summary').bounding_box()
            chart = page.locator('.chart-container').bounding_box()
            assert summary['y'] >= heading['y'] + heading['height'], f'Chart summary overlap at {width}px'
            assert chart['y'] >= summary['y'] + summary['height'], f'Chart overlap at {width}px'
        page.set_viewport_size({"width": 390, "height": 844})
        page.screenshot(path=str(Path(tempfile.gettempdir()) / "ritmo-mobile.png"), full_page=True)
        page.locator("#add-habit").click()
        expect(page.locator("#habit-dialog")).to_be_visible()
        page.keyboard.press("Escape")
        expect(page.locator("#habit-dialog")).not_to_be_visible()

        # Safe rendering and the fully empty state.
        for habit in page.request.get(url+'/api/state').json()['habits']:
            response=page.request.delete(url+'/api/habits/'+habit['id'], data={})
            assert response.ok
        page.reload()
        expect(page.locator('#connection-panel')).not_to_be_visible()
        expect(page.locator(".empty-habits")).to_be_visible()
        expect(page.locator("#today-percent")).to_have_text("0% от цели")
        page.locator("#add-habit").click()
        page.locator("#habit-name").fill('<img src=x onerror="window.bad=true">')
        page.locator("#save-habit").click()
        assert page.locator(".habit-name img").count() == 0
        assert page.evaluate("window.bad === undefined")
        assert not errors, errors
        print(json.dumps({"result": "PASS", "browser_errors": errors, "responsive_widths": layouts}, ensure_ascii=True))
        browser.close()


def main():
    with tempfile.TemporaryDirectory() as directory:
        server = ThreadingHTTPServer(('127.0.0.1', 0), QuietHandler)
        server.store = Store(Path(directory) / 'browser.sqlite3')
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            run_checks(f'http://127.0.0.1:{server.server_port}')
        finally:
            server.shutdown()
            server.server_close()
            thread.join()


if __name__ == "__main__":
    main()
