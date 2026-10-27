"""SQLite unit of work, schema initialization and profile persistence."""
import sqlite3
import re
from contextlib import contextmanager
from pathlib import Path
from backend.app.core.auth import AuthError
from backend.app.core.validation import today, valid_date, text_value
from backend.app.services import hydration, finance, organizer, relationships, day_tasks, wishlist, focus

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


