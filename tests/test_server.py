import json
import sqlite3
import sys
import tempfile
import threading
import unittest
import uuid
from concurrent.futures import ThreadPoolExecutor
from http.cookies import SimpleCookie
from contextlib import closing
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from backend.app.api.http import Handler
from backend.app.persistence.store import Store
from backend.app.main import ThreadingHTTPServer
from backend.app.core.validation import today
from backend.app.core.auth import Auth


class QuietHandler(Handler):
    def log_message(self, *args):
        pass


class ServerFixture(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.database = Path(self.directory.name) / 'test.sqlite3'
        self.auth = Auth('test-key-with-at-least-thirty-two-bytes', prefix='ritmo-test:'+uuid.uuid4().hex+':')
        self.token = None
        self.cookie = ''
        self.start_server()
        self.request('/api/auth/register', 'POST', {'email':'test@example.com','name':'Test','password':'correct-password'})

    def start_server(self):
        self.server = ThreadingHTTPServer(('127.0.0.1', 0), QuietHandler)
        self.server.store = Store(self.database)
        self.server.auth = self.auth
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.url = f'http://127.0.0.1:{self.server.server_port}'

    def stop_server(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join()

    def tearDown(self):
        self.stop_server()
        self.directory.cleanup()
        keys=list(self.auth.redis.scan_iter(self.auth.prefix+'*'))
        if keys:self.auth.redis.delete(*keys)
        self.auth.redis.close()

    def request(self, path='/api/state', method='GET', data=None, **headers):
        body = None if data is None else json.dumps(data).encode()
        request = Request(self.url + path, data=body, method=method,
                          headers={'Content-Type': 'application/json', **({'Authorization':'Bearer '+self.token} if self.token else {}),
                                   **({'Cookie':self.cookie} if self.cookie else {}), **headers})
        try:
            response = urlopen(request, timeout=5)
        except HTTPError as error:
            response = error
        with response:
            cookie=response.headers.get('Set-Cookie')
            if cookie:self.cookie=cookie.split(';',1)[0]
            data=json.loads(response.read())
            if data.get('accessToken'):self.token=data['accessToken']
            return response.status, data

    def habit(self, **values):
        return dict(id='reading', name='Read', category='Development', emoji='📖', color='#9772db', **values)


class ApiTests(ServerFixture):
    def test_parallel_asset_requests_are_all_served(self):
        paths=['/styles.css','/app.js','/finance.js','/water.js','/account.js','/finance.css','/achievements.css']*4
        def fetch(path):
            with urlopen(self.url+path,timeout=8) as response:
                self.assertTrue(response.read())
                return response.status
        with ThreadPoolExecutor(max_workers=20) as pool:
            self.assertTrue(all(status==200 for status in pool.map(fetch,paths)))

    def test_full_lifecycle_and_persistence_after_restart(self):
        self.assertFalse(self.request()[1]['initialized'])
        status, state = self.request('/api/habits', 'POST', self.habit())
        self.assertEqual(status, 200)
        self.assertEqual(state['habits'][0]['createdAt'], today())
        path = '/api/habits/reading/days/' + today()
        self.assertEqual(self.request(path, 'PUT', {'completed': True})[0], 200)
        self.stop_server()
        self.start_server()
        self.assertEqual(self.request()[1]['habits'][0]['logs'], [today()])
        details = self.habit()
        details['name'] = 'Read 20 minutes'
        self.assertEqual(self.request('/api/habits/reading', 'PATCH', details)[0], 200)
        self.assertEqual(self.request()[1]['habits'][0]['logs'], [today()])
        self.request(path, 'PUT', {'completed': False})
        with closing(sqlite3.connect(self.database)) as db:
            self.assertEqual(db.execute('SELECT completed FROM profile_days').fetchone()[0], 0)
        self.assertEqual(self.request()[1]['habits'][0]['logs'], [])
        self.assertEqual(self.request('/api/habits/reading', 'DELETE', {})[0], 200)
        with closing(sqlite3.connect(self.database)) as db:
            self.assertEqual(db.execute('SELECT COUNT(*) FROM profile_days').fetchone()[0], 0)

    def test_import_is_atomic_and_never_overwrites_existing_data(self):
        legacy = self.habit(logs=['2026-01-01', '2026-01-02'])
        status, state = self.request('/api/import', 'POST', {'habits': [legacy]})
        self.assertEqual(status, 200)
        self.assertEqual(state['habits'][0]['createdAt'], '2026-01-01')
        self.assertEqual(self.request('/api/import', 'POST', {'habits': []})[1]['habits'], state['habits'])

    def test_invalid_import_rolls_back(self):
        bad = self.habit()
        bad['id'] = 'bad'
        bad['logs'] = ['not-a-date']
        self.assertEqual(self.request('/api/import', 'POST', {'habits': [self.habit(), bad]})[0], 400)
        self.assertEqual(self.request()[1]['habits'], [])
        self.assertFalse(self.request()[1]['initialized'])

    def test_status_validation_and_creation_boundary(self):
        self.request('/api/habits', 'POST', self.habit())
        self.assertEqual(self.request('/api/habits/reading/days/2000-01-01', 'PUT', {'completed': True})[0], 400)
        self.assertEqual(self.request('/api/habits/reading/days/2999-01-01', 'PUT', {'completed': True})[0], 400)
        path = '/api/habits/reading/days/' + today()
        self.assertEqual(self.request(path, 'PUT', {'completed': 'true'})[0], 400)
        self.assertEqual(self.request(path, 'PUT', {'completed': 1})[0], 400)
        self.assertEqual(self.request()[1]['habits'][0]['logs'], [])

    def test_separate_habit_updates_do_not_lose_other_changes(self):
        self.request('/api/habits', 'POST', self.habit())
        other = self.habit()
        other['id'] = 'water'
        self.request('/api/habits', 'POST', other)
        for habit_id in ['reading', 'water']:
            self.request(f'/api/habits/{habit_id}/days/{today()}', 'PUT', {'completed': True})
        self.assertTrue(all(h['logs'] == [today()] for h in self.request()[1]['habits']))

    def test_database_and_sources_are_not_public(self):
        for path in ['/data/ritmo.sqlite3', '/server.py', '/tests/test_server.py', '/../README.md']:
            self.assertEqual(self.request(path)[0], 404)
        status, _ = self.request('/api/habits', 'POST', self.habit(), Origin='https://example.com')
        self.assertEqual(status, 403)

    def test_profiles_are_isolated_even_with_the_same_habit_id(self):
        self.request('/api/habits','POST',self.habit())
        self.request('/api/habits/reading/days/'+today(),'PUT',{'completed':True})
        first_token=self.token
        self.request('/api/auth/register','POST',{'email':'other@example.com','name':'Other','password':'other-password'})
        self.assertEqual(self.request()[1]['habits'],[])
        self.assertEqual(self.request('/api/habits/reading','DELETE',{})[0],404)
        self.request('/api/habits','POST',self.habit())
        self.assertEqual(self.request()[1]['habits'][0]['logs'],[])
        self.token=first_token
        self.assertEqual(self.request()[1]['habits'][0]['logs'],[today()])

    def test_unauthorized_and_logged_out_requests_are_rejected(self):
        token=self.token
        self.token=None
        self.assertEqual(self.request()[0],401)
        self.assertEqual(self.request('/api/habits','POST',self.habit())[0],401)
        self.token=token
        self.request('/api/auth/logout','POST',{})
        self.assertEqual(self.request()[0],401)

    def test_registration_login_and_http_only_refresh(self):
        user=self.request()[1]['user']
        self.assertNotIn('password_hash',user)
        self.request('/api/auth/logout','POST',{})
        self.assertEqual(self.request('/api/auth/login','POST',{'email':'TEST@example.com','password':'bad-password'})[0],401)
        self.assertEqual(self.request('/api/auth/login','POST',{'email':'TEST@example.com','password':'correct-password'})[0],200)
        self.assertEqual(self.request('/api/auth/refresh','POST',{})[0],200)
        with closing(sqlite3.connect(self.database)) as db:
            hashed=db.execute('SELECT password_hash FROM users').fetchone()[0]
            self.assertNotEqual(hashed,'correct-password')

    def test_first_profile_can_explicitly_adopt_legacy_database(self):
        with self.server.store.connect() as db:
            db.execute('DELETE FROM users')
            db.execute("INSERT INTO habits VALUES ('old','Old','Development','📖','#9772db',?,0)",(today(),))
            db.execute("INSERT INTO habit_days VALUES ('old',?,1)",(today(),))
        self.assertTrue(self.request('/api/auth/bootstrap')[1]['legacyAvailable'])
        self.request('/api/auth/register','POST',{'email':'first@example.com','name':'First','password':'first-password','importLegacy':True})
        self.assertEqual(self.request()[1]['habits'][0]['logs'],[today()])
        self.request('/api/auth/register','POST',{'email':'second@example.com','name':'Second','password':'second-password','importLegacy':True})
        self.assertEqual(self.request()[1]['habits'],[])


if __name__ == '__main__':
    unittest.main()
