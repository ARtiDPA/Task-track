"""Per-profile water settings, daily goals, and individually reversible entries."""
import math
import re
from datetime import datetime, timezone


def initialize(db):
    db.executescript('''
        CREATE TABLE IF NOT EXISTS water_profiles (
            user_id TEXT PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
            height_cm REAL NOT NULL,
            weight_kg REAL NOT NULL,
            goal_ml INTEGER NOT NULL,
            created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS water_goals (
            user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            day TEXT NOT NULL,
            goal_ml INTEGER NOT NULL,
            PRIMARY KEY(user_id,day)
        );
        CREATE TABLE IF NOT EXISTS water_entries (
            user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            id TEXT NOT NULL,
            day TEXT NOT NULL,
            amount_ml INTEGER NOT NULL CHECK(amount_ml>0),
            created_at TEXT NOT NULL,
            PRIMARY KEY(user_id,id)
        );
        CREATE INDEX IF NOT EXISTS water_day_index ON water_entries(user_id,day);
    ''')


def number(data, key, minimum, maximum, integer=False):
    value=data.get(key)
    if type(value) not in (int,float) or not math.isfinite(value) or not minimum<=value<=maximum:
        raise ValueError(f'Неверное значение {key}: от {minimum} до {maximum}.')
    if integer and value!=int(value):
        raise ValueError('Объём указывается в целых миллилитрах.')
    return int(value) if integer else value


def settings(db,user_id,data,day):
    height=number(data,'heightCm',100,240)
    weight=number(data,'weightKg',30,300)
    goal=number(data,'goalMl',250,5000,integer=True)
    if data.get('adult') is not True:
        raise ValueError('Этот ориентир предназначен для взрослых.')
    db.execute('''INSERT INTO water_profiles VALUES (?,?,?,?,?)
                  ON CONFLICT(user_id) DO UPDATE SET height_cm=excluded.height_cm,weight_kg=excluded.weight_kg,goal_ml=excluded.goal_ml''',
               (user_id,height,weight,goal,day))
    db.execute('INSERT INTO water_goals VALUES (?,?,?) ON CONFLICT(user_id,day) DO UPDATE SET goal_ml=excluded.goal_ml',
               (user_id,day,goal))


def add(db,user_id,data,day):
    profile=db.execute('SELECT * FROM water_profiles WHERE user_id=?',(user_id,)).fetchone()
    if not profile:
        raise ValueError('Сначала настрой свой трекер воды.')
    amount=number(data,'amountMl',25,2000,integer=True)
    entry_id=data.get('id')
    if not isinstance(entry_id,str) or not re.fullmatch(r'[a-zA-Z0-9_-]{1,100}',entry_id):
        raise ValueError('Неверный идентификатор записи.')
    old=db.execute('SELECT * FROM water_entries WHERE user_id=? AND id=?',(user_id,entry_id)).fetchone()
    if old:
        if old['day']!=day or old['amount_ml']!=amount:
            raise ValueError('Эта запись уже сохранена с другим объёмом.')
        return
    total=db.execute('SELECT COALESCE(SUM(amount_ml),0) FROM water_entries WHERE user_id=? AND day=?',(user_id,day)).fetchone()[0]
    if total+amount>10000:
        raise ValueError('Проверь объём: за день уже записано очень много жидкости.')
    db.execute('INSERT OR IGNORE INTO water_goals VALUES (?,?,?)',(user_id,day,profile['goal_ml']))
    db.execute('INSERT INTO water_entries VALUES (?,?,?,?,?)',
               (user_id,entry_id,day,amount,datetime.now(timezone.utc).isoformat()))


def remove(db,user_id,entry_id):
    cursor=db.execute('DELETE FROM water_entries WHERE user_id=? AND id=?',(user_id,entry_id))
    return cursor.rowcount>0


def state(db,user_id,day):
    profile=db.execute('SELECT * FROM water_profiles WHERE user_id=?',(user_id,)).fetchone()
    goal_row=db.execute('SELECT goal_ml FROM water_goals WHERE user_id=? AND day=?',(user_id,day)).fetchone()
    goal=goal_row[0] if goal_row else profile['goal_ml'] if profile else 1750
    entries=[dict(id=row['id'],amountMl=row['amount_ml'],createdAt=row['created_at'])
             for row in db.execute('SELECT * FROM water_entries WHERE user_id=? AND day=? ORDER BY created_at,id',(user_id,day))]
    daily=list(db.execute('''SELECT e.day,SUM(e.amount_ml) AS total,g.goal_ml FROM water_entries e
                             JOIN water_goals g ON g.user_id=e.user_id AND g.day=e.day
                             WHERE e.user_id=? GROUP BY e.day ORDER BY e.day''',(user_id,)))
    return {
        'profile':dict(heightCm=profile['height_cm'],weightKg=profile['weight_kg'],goalMl=profile['goal_ml']) if profile else None,
        'day':day,'goalMl':goal,'totalMl':sum(entry['amountMl'] for entry in entries),'glassMl':250,'entries':entries,
        'history':[dict(day=row['day'],totalMl=row['total'],goalMl=row['goal_ml']) for row in daily[-365:]],
        'summary':dict(activeDays=len(daily),goalDays=sum(row['total']>=row['goal_ml'] for row in daily),entries=db.execute('SELECT COUNT(*) FROM water_entries WHERE user_id=?',(user_id,)).fetchone()[0])
    }
