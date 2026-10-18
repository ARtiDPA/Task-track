"""Ritmo local server and SQLite API. Run: python server.py"""
import argparse
import json
import mimetypes
import os
import re
import sqlite3
from contextlib import contextmanager
from datetime import date, datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlsplit

ROOT = Path(__file__).resolve().parent
MOSCOW = timezone(timedelta(hours=3))


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
                PRAGMA user_version=1;
            ''')

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

    def state(self, db):
        habits = []
        logs = {}
        for row in db.execute('SELECT habit_id, day FROM habit_days WHERE completed=1 ORDER BY day'):
            logs.setdefault(row['habit_id'], []).append(row['day'])
        for row in db.execute('SELECT * FROM habits ORDER BY position, id'):
            habits.append(dict(id=row['id'], name=row['name'], category=row['category'],
                               emoji=row['emoji'], color=row['color'], createdAt=row['created_at'],
                               logs=logs.get(row['id'], [])))
        initialized = db.execute("SELECT 1 FROM metadata WHERE key='initialized'").fetchone() is not None
        return {'habits': habits, 'initialized': initialized}

    def insert_habit(self, db, data, position, importing=False):
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
        db.execute('INSERT INTO habits VALUES (?,?,?,?,?,?,?)',
                   (habit_id, name, category, emoji, color, created, position))
        db.executemany('INSERT INTO habit_days VALUES (?,?,1)', [(habit_id, day) for day in logs])


class Handler(BaseHTTPRequestHandler):
    server_version = 'Ritmo/1.0'

    def send_json(self, status, value):
        body = json.dumps(value, ensure_ascii=False).encode('utf-8')
        self.send_response(status)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Cache-Control', 'no-store')
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.end_headers()
        self.wfile.write(body)

    def read_json(self):
        origin = self.headers.get('Origin')
        if origin and origin != 'http://' + self.headers.get('Host', ''):
            raise PermissionError('Недопустимый источник запроса')
        if self.headers.get_content_type() != 'application/json':
            raise ValueError('Ожидается JSON')
        length = int(self.headers.get('Content-Length', '0'))
        if not 0 < length <= 2_000_000:
            raise ValueError('Недопустимый размер запроса')
        data = json.loads(self.rfile.read(length))
        if not isinstance(data, dict):
            raise ValueError('Ожидается объект JSON')
        return data

    def do_GET(self):
        path = urlsplit(self.path).path
        if path == '/api/state':
            with self.server.store.connect() as db:
                db.execute('BEGIN')
                self.send_json(200, self.server.store.state(db))
            return
        if path == '/favicon.ico':
            self.send_response(204)
            self.end_headers()
            return
        files = {'/': 'index.html', '/index.html': 'index.html', '/app.js': 'app.js', '/metrics.js': 'metrics.js', '/styles.css': 'styles.css'}
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
            with store.connect() as db:
                db.execute('BEGIN IMMEDIATE')
                if self.command == 'POST' and path == '/api/import':
                    # Atomic first-run import never replaces an existing database.
                    if not store.state(db)['initialized']:
                        habits = data.get('habits')
                        if not isinstance(habits, list) or len(habits) > 1000:
                            raise ValueError('Неверный список привычек')
                        for position, habit in enumerate(habits):
                            if not isinstance(habit, dict):
                                raise ValueError('Неверная привычка')
                            store.insert_habit(db, habit, position, importing=True)
                        db.execute("INSERT INTO metadata VALUES ('initialized','1')")
                elif self.command == 'POST' and path == '/api/habits':
                    position = db.execute('SELECT COALESCE(MAX(position),-1)+1 FROM habits').fetchone()[0]
                    store.insert_habit(db, data, position)
                    db.execute("INSERT OR IGNORE INTO metadata VALUES ('initialized','1')")
                elif len(parts) >= 3 and parts[:2] == ['api', 'habits']:
                    habit = db.execute('SELECT * FROM habits WHERE id=?', (parts[2],)).fetchone()
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
                        db.execute('UPDATE habits SET name=?,category=?,emoji=?,color=? WHERE id=?',
                                   (name, category, emoji, color, parts[2]))
                    elif self.command == 'DELETE' and len(parts) == 3:
                        db.execute('DELETE FROM habits WHERE id=?', (parts[2],))
                    elif self.command == 'PUT' and len(parts) == 5 and parts[3] == 'days':
                        day = valid_date(parts[4])
                        if day < habit['created_at']:
                            raise ValueError('Привычка ещё не существовала в этот день')
                        if type(data.get('completed')) is not bool:
                            raise ValueError('Укажите статус выполнения')
                        db.execute('INSERT INTO habit_days VALUES (?,?,?) ON CONFLICT(habit_id,day) DO UPDATE SET completed=excluded.completed',
                                   (parts[2], day, int(data['completed'])))
                    else:
                        self.send_json(404, {'error': 'Метод не найден'})
                        return
                else:
                    self.send_json(404, {'error': 'Метод не найден'})
                    return
                result = store.state(db)
            # Send success only after the transaction has committed to disk.
            self.send_json(200, result)
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


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port', type=int, default=5173)
    parser.add_argument('--database', default=os.environ.get('RITMO_DB', str(ROOT / 'data' / 'ritmo.sqlite3')))
    args = parser.parse_args()
    server = ThreadingHTTPServer(('127.0.0.1', args.port), Handler)
    server.store = Store(args.database)
    print(f'Ritmo: http://localhost:{server.server_port}', flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == '__main__':
    main()
