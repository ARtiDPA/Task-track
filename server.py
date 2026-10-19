"""Ritmo local server and SQLite API. Run: python server.py"""
import argparse
import json
import mimetypes
import os
import re
import sqlite3
import uuid
from http.cookies import SimpleCookie, CookieError
from contextlib import contextmanager
from datetime import date, datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer as BaseThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlsplit

import redis
import hydration
import finance
import organizer
import relationships
import day_tasks
import wishlist
import focus
from auth import Auth, AuthError, SESSION_SECONDS, email_value, password_value, hash_password, verify_password, load_secret

ROOT = Path(__file__).resolve().parent
MOSCOW = timezone(timedelta(hours=3))


class ThreadingHTTPServer(BaseThreadingHTTPServer):
    # Chromium requests the independent styles and scripts concurrently on reload.
    request_queue_size = 128


def today():
    return datetime.now(MOSCOW).date().isoformat()


def valid_date(value):
    if not isinstance(value, str) or not re.fullmatch(r'\d{4}-\d{2}-\d{2}', value):
        raise ValueError('Неверная дата')
    date.fromisoformat(value)
    if value > today():
        raise ValueError('Нельзя отмечать будущие дни')
    return value


def text_value(data, key, limit):
    value = data.get(key)
    if not isinstance(value, str) or not value.strip() or len(value.strip()) > limit:
        raise ValueError(f'Неверное поле: {key}')
    return value.strip()


class Store:
    def __init__(self, path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as db:
            db.execute('PRAGMA journal_mode=WAL')
            db.executescript('''
                CREATE TABLE IF NOT EXISTS metadata (key TEXT PRIMARY KEY, value TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS habits (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    category TEXT NOT NULL,
                    emoji TEXT NOT NULL,
                    color TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    position INTEGER NOT NULL
                );
                CREATE TABLE IF NOT EXISTS habit_days (
                    habit_id TEXT NOT NULL REFERENCES habits(id) ON DELETE CASCADE,
                    day TEXT NOT NULL,
                    completed INTEGER NOT NULL CHECK(completed IN (0,1)),
                    PRIMARY KEY(habit_id, day)
                );
                CREATE TABLE IF NOT EXISTS users (
                    id TEXT PRIMARY KEY,
                    email TEXT NOT NULL UNIQUE,
                    name TEXT NOT NULL,
                    password_hash TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    initialized INTEGER NOT NULL DEFAULT 0
                );
                CREATE TABLE IF NOT EXISTS profile_habits (
                    user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                    id TEXT NOT NULL,
                    name TEXT NOT NULL,
                    category TEXT NOT NULL,
                    emoji TEXT NOT NULL,
                    color TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    position INTEGER NOT NULL,
                    PRIMARY KEY(user_id,id)
                );
                CREATE TABLE IF NOT EXISTS profile_days (
                    user_id TEXT NOT NULL,
                    habit_id TEXT NOT NULL,
                    day TEXT NOT NULL,
                    completed INTEGER NOT NULL CHECK(completed IN (0,1)),
                    PRIMARY KEY(user_id,habit_id,day),
                    FOREIGN KEY(user_id,habit_id) REFERENCES profile_habits(user_id,id) ON DELETE CASCADE
                );
                PRAGMA user_version=2;
            ''')
            hydration.initialize(db)
            finance.initialize(db)
            organizer.initialize(db)
            relationships.initialize(db,today())
            day_tasks.initialize(db)
            wishlist.initialize(db)
            focus.initialize(db)
            db.execute('PRAGMA user_version=12')

    @contextmanager
    def connect(self):
        db = sqlite3.connect(self.path, timeout=10)
        db.row_factory = sqlite3.Row
        db.execute('PRAGMA foreign_keys=ON')
        try:
            with db:
                yield db
        finally:
            db.close()

    def user(self, db, user_id):
        row = db.execute('SELECT id,email,name,created_at,initialized FROM users WHERE id=?', (user_id,)).fetchone()
        if not row:
            raise AuthError()
        return dict(id=row['id'], email=row['email'], name=row['name'], createdAt=row['created_at'])

    def legacy_available(self, db):
        return not db.execute('SELECT 1 FROM users LIMIT 1').fetchone() and bool(
            db.execute("SELECT 1 FROM metadata WHERE key='initialized'").fetchone() or
            db.execute('SELECT 1 FROM habits LIMIT 1').fetchone())

    def state(self, db, user_id):
        habits = []
        logs = {}
        for row in db.execute('SELECT habit_id, day FROM profile_days WHERE user_id=? AND completed=1 ORDER BY day', (user_id,)):
            logs.setdefault(row['habit_id'], []).append(row['day'])
        for row in db.execute('SELECT * FROM profile_habits WHERE user_id=? ORDER BY position, id', (user_id,)):
            habits.append(dict(id=row['id'], name=row['name'], category=row['category'],
                               emoji=row['emoji'], color=row['color'], createdAt=row['created_at'],
                               logs=logs.get(row['id'], [])))
        user = self.user(db, user_id)
        initialized = bool(db.execute('SELECT initialized FROM users WHERE id=?', (user_id,)).fetchone()[0])
        extras=organizer.state(db,user_id)
        ledger=finance.state(db,user_id)
        ledger['reservedKopecks']=extras['reservedKopecks']
        ledger['freeBalanceKopecks']=ledger['balanceKopecks']-extras['reservedKopecks']
        return {'user': user, 'habits': habits, 'initialized': initialized, 'water': hydration.state(db,user_id,today()), 'finance':ledger,'organizer':extras,'relationships':relationships.state(db,user_id),'tasks':day_tasks.state(db,user_id),'wishlist':wishlist.state(db,user_id),'focus':focus.state(db,user_id)}

    def insert_habit(self, db, user_id, data, position, importing=False):
        habit_id = text_value(data, 'id', 100)
        if not re.fullmatch(r'[a-zA-Z0-9_-]+', habit_id):
            raise ValueError('Неверный идентификатор привычки')
        name = text_value(data, 'name', 60)
        category = text_value(data, 'category', 40)
        emoji = text_value(data, 'emoji', 32)
        color = text_value(data, 'color', 7)
        if not re.fullmatch(r'#[0-9a-fA-F]{6}', color):
            raise ValueError('Неверный цвет')
        logs = data.get('logs', []) if importing else []
        if not isinstance(logs, list) or len(logs) > 20000:
            raise ValueError('Неверная история привычки')
        logs = sorted(set(valid_date(day) for day in logs))
        # Old localStorage had no creation date: preserve the earliest recorded day.
        created = valid_date(data.get('createdAt') or (logs[0] if logs else today())) if importing else today()
        if any(day < created for day in logs):
            raise ValueError('Отметка не может быть раньше создания привычки')
        db.execute('INSERT INTO profile_habits VALUES (?,?,?,?,?,?,?,?)',
                   (user_id, habit_id, name, category, emoji, color, created, position))
        db.executemany('INSERT INTO profile_days VALUES (?,?,?,1)', [(user_id, habit_id, day) for day in logs])


class Handler(BaseHTTPRequestHandler):
    server_version = 'Ritmo/1.0'

    def send_json(self, status, value, cookie=None):
        body = json.dumps(value, ensure_ascii=False).encode('utf-8')
        self.send_response(status)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Cache-Control', 'no-store')
        self.send_header('X-Content-Type-Options', 'nosniff')
        if cookie is not None:
            self.send_header('Set-Cookie', cookie)
        self.end_headers()
        self.wfile.write(body)

    def read_json(self):
        length = int(self.headers.get('Content-Length', '0'))
        if not 0 < length <= 2_000_000:
            raise ValueError('Недопустимый размер запроса')
        body = self.rfile.read(length)
        origin = self.headers.get('Origin')
        if origin and origin != 'http://' + self.headers.get('Host', ''):
            raise PermissionError('Недопустимый источник запроса')
        if self.headers.get_content_type() != 'application/json':
            raise ValueError('Ожидается JSON')
        data = json.loads(body)
        if not isinstance(data, dict):
            raise ValueError('Ожидается объект JSON')
        return data

    def refresh_cookie(self):
        try:
            cookies = SimpleCookie(self.headers.get('Cookie', ''))
            return cookies['ritmo_refresh'].value if 'ritmo_refresh' in cookies else None
        except CookieError:
            return None

    def cookie_header(self, token=None):
        value = f'ritmo_refresh={token or ""}; HttpOnly; SameSite=Strict; Path=/api/auth; Max-Age={SESSION_SECONDS if token else 0}'
        if os.environ.get('RITMO_COOKIE_SECURE') == '1':
            value += '; Secure'
        return value

    def current_user(self):
        return self.server.auth.verify(self.headers.get('Authorization'))

    def do_GET(self):
        try:
            self.get()
        except AuthError as error:
            self.send_json(error.status, {'error': str(error)})
        except (redis.RedisError, sqlite3.Error):
            self.send_json(503, {'error': 'Хранилище временно недоступно. Попробуй ещё раз.'})

    def get(self):
        path = urlsplit(self.path).path
        if path == '/api/auth/bootstrap':
            with self.server.store.connect() as db:
                self.send_json(200, {'legacyAvailable': self.server.store.legacy_available(db)})
            return
        if path == '/api/auth/me':
            user_id = self.current_user()
            with self.server.store.connect() as db:
                self.send_json(200, {'user': self.server.store.user(db, user_id)})
            return
        if path == '/api/state':
            user_id = self.current_user()
            with self.server.store.connect() as db:
                db.execute('BEGIN')
                self.send_json(200, self.server.store.state(db, user_id))
            return
        if path == '/favicon.ico':
            self.send_response(204)
            self.end_headers()
            return
        files = {'/': 'index.html', '/index.html': 'index.html', '/app.js': 'app.js', '/metrics.js': 'metrics.js', '/storage.js': 'storage.js', '/emoji-catalog.js': 'emoji-catalog.js', '/styles.css': 'styles.css', '/account.css': 'account.css', '/account.js': 'account.js', '/achievements.js': 'achievements.js', '/achievements.css': 'achievements.css', '/water.js': 'water.js', '/water.css': 'water.css', '/finance.js': 'finance.js', '/finance.css': 'finance.css', '/finance-math.js': 'finance-math.js', '/schedule.js':'schedule.js', '/planner-math.js':'planner-math.js', '/money-organizer.js':'money-organizer.js', '/planner.js':'planner.js', '/calendar.js':'calendar.js', '/organizer.css':'organizer.css', '/relationships.js':'relationships.js', '/relationships.css':'relationships.css', '/day-tasks.js':'day-tasks.js', '/day-tasks.css':'day-tasks.css', '/wishlist.js':'wishlist.js', '/wishlist.css':'wishlist.css', '/focus-sound.js':'focus-sound.js', '/focus.js':'focus.js', '/focus.css':'focus.css', '/focus-math.js':'focus-math.js'}
        if path not in files:
            self.send_json(404, {'error': 'Страница не найдена'})
            return
        file = ROOT / files[path]
        body = file.read_bytes()
        self.send_response(200)
        self.send_header('Content-Type', (mimetypes.guess_type(file)[0] or 'application/octet-stream') + '; charset=utf-8')
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Cache-Control', 'no-cache')
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.end_headers()
        self.wfile.write(body)

    def mutate(self):
        try:
            data = self.read_json()
            path = urlsplit(self.path).path
            parts = [unquote(part) for part in path.strip('/').split('/')]
            store = self.server.store
            if path.startswith('/api/auth/'):
                self.auth_action(path, data)
                return
            user_id = self.current_user()
            with store.connect() as db:
                db.execute('BEGIN IMMEDIATE')
                store.user(db, user_id)
                if parts[:2]==['api','focus']:
                    if not focus.dispatch(db,user_id,parts,self.command,data):
                        self.send_json(404,{'error':'Сессия не найдена.'});return
                elif parts[:2]==['api','wishlist']:
                    if not wishlist.dispatch(db,user_id,parts,self.command,data,today()):
                        self.send_json(404,{'error':'Желание не найдено.'});return
                elif parts[:2]==['api','tasks']:
                    if not day_tasks.dispatch(db,user_id,parts,self.command,data):
                        self.send_json(404,{'error':'Задача не найдена.'});return
                elif parts[:2]==['api','relationships']:
                    if not relationships.dispatch(db,user_id,parts,self.command,data,today()):
                        self.send_json(404,{'error':'Запись не найдена.'});return
                elif parts[:2]==['api','organizer']:
                    if not organizer.dispatch(db,user_id,parts,self.command,data,today()):
                        self.send_json(404,{'error':'Запись не найдена.'});return
                elif self.command=='PUT' and path=='/api/finance/settings':
                    finance.settings(db,user_id,data)
                elif self.command=='POST' and path=='/api/finance/categories':
                    finance.category(db,user_id,data)
                elif self.command=='PUT' and len(parts)==5 and parts[:3]==['api','finance','categories'] and parts[4]=='budget':
                    if not finance.budget(db,user_id,parts[3],data):
                        self.send_json(404,{'error':'Категория не найдена.'});return
                elif self.command=='POST' and path=='/api/finance/transactions':
                    finance.transaction(db,user_id,data,today())
                elif len(parts)==4 and parts[:3]==['api','finance','transactions'] and self.command in ('PATCH','DELETE'):
                    changed=finance.transaction(db,user_id,data,today(),parts[3]) if self.command=='PATCH' else finance.remove(db,user_id,parts[3])
                    if not changed:
                        self.send_json(404,{'error':'Операция не найдена.'});return
                elif self.command == 'PUT' and path == '/api/water/settings':
                    hydration.settings(db,user_id,data,today())
                elif self.command == 'POST' and path == '/api/water/entries':
                    hydration.add(db,user_id,data,today())
                elif self.command == 'DELETE' and len(parts)==4 and parts[:3]==['api','water','entries']:
                    if not hydration.remove(db,user_id,parts[3]):
                        self.send_json(404,{'error':'Запись не найдена.'})
                        return
                elif self.command == 'POST' and path == '/api/import':
                    # Atomic first-run import never replaces an existing database.
                    if not store.state(db, user_id)['initialized']:
                        habits = data.get('habits')
                        if not isinstance(habits, list) or len(habits) > 1000:
                            raise ValueError('Неверный список привычек')
                        for position, habit in enumerate(habits):
                            if not isinstance(habit, dict):
                                raise ValueError('Неверная привычка')
                            store.insert_habit(db, user_id, habit, position, importing=True)
                        db.execute('UPDATE users SET initialized=1 WHERE id=?', (user_id,))
                elif self.command == 'POST' and path == '/api/habits':
                    position = db.execute('SELECT COALESCE(MAX(position),-1)+1 FROM profile_habits WHERE user_id=?', (user_id,)).fetchone()[0]
                    store.insert_habit(db, user_id, data, position)
                    db.execute('UPDATE users SET initialized=1 WHERE id=?', (user_id,))
                elif len(parts) >= 3 and parts[:2] == ['api', 'habits']:
                    habit = db.execute('SELECT * FROM profile_habits WHERE user_id=? AND id=?', (user_id, parts[2])).fetchone()
                    if not habit:
                        self.send_json(404, {'error': 'Привычка не найдена. Обновите страницу.'})
                        return
                    if self.command == 'PATCH' and len(parts) == 3:
                        name = text_value(data, 'name', 60)
                        category = text_value(data, 'category', 40)
                        emoji = text_value(data, 'emoji', 32)
                        color = text_value(data, 'color', 7)
                        if not re.fullmatch(r'#[0-9a-fA-F]{6}', color):
                            raise ValueError('Неверный цвет')
                        db.execute('UPDATE profile_habits SET name=?,category=?,emoji=?,color=? WHERE user_id=? AND id=?',
                                   (name, category, emoji, color, user_id, parts[2]))
                    elif self.command == 'DELETE' and len(parts) == 3:
                        db.execute('DELETE FROM profile_habits WHERE user_id=? AND id=?', (user_id, parts[2]))
                    elif self.command == 'PUT' and len(parts) == 5 and parts[3] == 'days':
                        day = valid_date(parts[4])
                        if day < habit['created_at']:
                            raise ValueError('Привычка ещё не существовала в этот день')
                        if type(data.get('completed')) is not bool:
                            raise ValueError('Укажите статус выполнения')
                        db.execute('INSERT INTO profile_days VALUES (?,?,?,?) ON CONFLICT(user_id,habit_id,day) DO UPDATE SET completed=excluded.completed',
                                   (user_id, parts[2], day, int(data['completed'])))
                    else:
                        self.send_json(404, {'error': 'Метод не найден'})
                        return
                else:
                    self.send_json(404, {'error': 'Метод не найден'})
                    return
                result = store.state(db, user_id)
            # Send success only after the transaction has committed to disk.
            self.send_json(200, result)
        except AuthError as error:
            self.send_json(error.status, {'error': str(error)})
        except redis.RedisError:
            self.send_json(503, {'error': 'Redis недоступен. Попробуй подключиться ещё раз.'})
        except PermissionError as error:
            self.send_json(403, {'error': str(error)})
        except (ValueError, TypeError, KeyError, UnicodeError) as error:
            self.send_json(400, {'error': str(error)})
        except sqlite3.IntegrityError:
            self.send_json(409, {'error': 'Такая привычка уже существует. Обновите страницу.'})
        except sqlite3.Error:
            self.send_json(503, {'error': 'Не удалось сохранить данные. Повторите попытку.'})

    do_POST = mutate
    do_PATCH = mutate
    do_PUT = mutate
    do_DELETE = mutate

    def auth_action(self, path, data):
        if self.command != 'POST':
            self.send_json(405, {'error': 'Используй POST.'})
            return
        auth, store = self.server.auth, self.server.store
        if path == '/api/auth/logout':
            auth.logout(self.refresh_cookie())
            self.send_json(200, {'ok': True}, self.cookie_header())
            return
        if path == '/api/auth/refresh':
            token, refresh, user_id = auth.refresh(self.refresh_cookie())
            with store.connect() as db:
                user = store.user(db, user_id)
            self.send_json(200, {'accessToken': token, 'user': user}, self.cookie_header(refresh))
            return
        if path not in ['/api/auth/register', '/api/auth/login']:
            self.send_json(404, {'error': 'Метод не найден'})
            return
        email = email_value(data)
        registering = path.endswith('/register')
        password = password_value(data, registering)
        auth.rate_limit('auth-ip', self.client_address[0], 100, 3600)
        auth.rate_limit('auth-email', email, 20, 600)
        if registering:
            name = text_value(data, 'name', 40)
            user_id = uuid.uuid4().hex
            password_hash = hash_password(password)
            with store.connect() as db:
                db.execute('BEGIN IMMEDIATE')
                if db.execute('SELECT 1 FROM users WHERE email=?', (email,)).fetchone():
                    raise AuthError('Этот email уже зарегистрирован. Войди в профиль.', 409)
                claim = data.get('importLegacy') is True and store.legacy_available(db)
                db.execute('INSERT INTO users VALUES (?,?,?,?,?,?)',
                           (user_id, email, name, password_hash, datetime.now(timezone.utc).isoformat(), int(claim)))
                finance.seed(db,user_id)
                if claim:
                    db.execute('INSERT INTO profile_habits SELECT ?,id,name,category,emoji,color,created_at,position FROM habits', (user_id,))
                    db.execute('INSERT INTO profile_days SELECT ?,habit_id,day,completed FROM habit_days', (user_id,))
                    db.execute("INSERT OR REPLACE INTO metadata VALUES ('legacy_claimed',?)", (user_id,))
                token, refresh = auth.session(user_id)
                user = store.user(db, user_id)
        else:
            with store.connect() as db:
                row = db.execute('SELECT id,password_hash FROM users WHERE email=?', (email,)).fetchone()
                if not verify_password(password, row['password_hash'] if row else auth.dummy_hash) or not row:
                    raise AuthError('Неверный email или пароль.')
                user_id = row['id']
                user = store.user(db, user_id)
            token, refresh = auth.session(user_id)
        self.send_json(200, {'accessToken': token, 'user': user}, self.cookie_header(refresh))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port', type=int, default=5173)
    parser.add_argument('--database', default=os.environ.get('RITMO_DB', str(ROOT / 'data' / 'ritmo.sqlite3')))
    args = parser.parse_args()
    server = ThreadingHTTPServer(('127.0.0.1', args.port), Handler)
    server.store = Store(args.database)
    server.auth = Auth(load_secret(Path(args.database).resolve().parent))
    server.auth.check()
    print(f'Ritmo: http://localhost:{server.server_port}', flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == '__main__':
    main()
