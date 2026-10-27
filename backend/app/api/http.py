"""HTTP endpoints, request validation, authentication and static responses."""
import json
import mimetypes
import os
import sqlite3
import uuid
import re
from datetime import datetime, timezone
from http.cookies import SimpleCookie, CookieError
from http.server import BaseHTTPRequestHandler
from urllib.parse import unquote, urlsplit
import redis
from backend.app.core.auth import AuthError, SESSION_SECONDS, email_value, password_value, hash_password, verify_password
from backend.app.core.config import ROOT, STATIC
from backend.app.core.validation import today, valid_date, text_value
from backend.app.services import hydration, finance, organizer, relationships, day_tasks, wishlist, focus

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
                # State reconciliation may finish a focus session and write rows.
                # Acquire the write lock before reading to avoid WAL snapshot upgrades.
                db.execute('BEGIN IMMEDIATE')
                self.send_json(200, self.server.store.state(db, user_id))
            return
        if path == '/favicon.ico':
            self.send_response(204)
            self.end_headers()
            return
        files = {'/category-search.js': 'category-search.js', '/nocturne.css': 'nocturne.css', '/nocturne.js': 'nocturne.js', '/': 'index.html', '/index.html': 'index.html', '/app.js': 'app.js', '/metrics.js': 'metrics.js', '/storage.js': 'storage.js', '/emoji-catalog.js': 'emoji-catalog.js', '/styles.css': 'styles.css', '/account.css': 'account.css', '/account.js': 'account.js', '/achievements.js': 'achievements.js', '/achievements.css': 'achievements.css', '/water.js': 'water.js', '/water.css': 'water.css', '/finance.js': 'finance.js', '/finance.css': 'finance.css', '/finance-math.js': 'finance-math.js', '/schedule.js':'schedule.js', '/planner-math.js':'planner-math.js', '/money-organizer.js':'money-organizer.js', '/planner.js':'planner.js', '/calendar.js':'calendar.js', '/organizer.css':'organizer.css', '/relationships.js':'relationships.js', '/relationships.css':'relationships.css', '/day-tasks.js':'day-tasks.js', '/day-tasks.css':'day-tasks.css', '/wishlist.js':'wishlist.js', '/wishlist.css':'wishlist.css', '/focus-sound.js':'focus-sound.js', '/focus.js':'focus.js', '/focus.css':'focus.css', '/focus-math.js':'focus-math.js'}
        if path not in files:
            self.send_json(404, {'error': 'Страница не найдена'})
            return
        name = files[path]
        file = ROOT / 'frontend' / 'templates' / name if name.endswith('.html') else STATIC / ('js' if name.endswith('.js') else 'css') / name
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


