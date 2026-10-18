"""Personal finance ledger. All amounts are integer kopecks, never floats."""
import re
from datetime import date, datetime, timezone

PRESETS = [
    ('groceries','Продукты','expense','🥗','#82b69c'),('cafes','Кафе и доставка','expense','☕','#d0aa7e'),
    ('home','Дом и счета','expense','🏡','#a68bd2'),('transport','Транспорт','expense','🚗','#87a9d2'),
    ('shopping','Покупки','expense','🛍️','#d29db5'),('health','Здоровье','expense','💊','#83b7b7'),
    ('fun','Развлечения','expense','🎬','#bf9cd7'),('subscriptions','Подписки','expense','📱','#a1abd7'),
    ('education','Образование','expense','📚','#c3ae78'),('travel','Путешествия','expense','🌍','#8ebbae'),
    ('other-expense','Другое','expense','✨','#b3a7c5'),('salary','Зарплата','income','💼','#76ad97'),
    ('freelance','Подработка','income','💻','#8eabd2'),('gifts','Подарки','income','🎁','#c49fb5'),
    ('other-income','Другие доходы','income','🌱','#a2b77d')
]


def initialize(db):
    db.executescript('''
        CREATE TABLE IF NOT EXISTS finance_settings (
            user_id TEXT PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
            opening_balance INTEGER NOT NULL DEFAULT 0,
            monthly_budget INTEGER NOT NULL DEFAULT 0
        );
        CREATE TABLE IF NOT EXISTS finance_categories (
            user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            id TEXT NOT NULL, name TEXT NOT NULL, kind TEXT NOT NULL CHECK(kind IN ('income','expense')),
            emoji TEXT NOT NULL, color TEXT NOT NULL, budget INTEGER NOT NULL DEFAULT 0,
            PRIMARY KEY(user_id,id)
        );
        CREATE TABLE IF NOT EXISTS finance_transactions (
            user_id TEXT NOT NULL, id TEXT NOT NULL, day TEXT NOT NULL,
            category_id TEXT NOT NULL, amount INTEGER NOT NULL CHECK(amount>0),
            note TEXT NOT NULL, created_at TEXT NOT NULL,
            PRIMARY KEY(user_id,id),
            FOREIGN KEY(user_id,category_id) REFERENCES finance_categories(user_id,id)
        );
        CREATE INDEX IF NOT EXISTS finance_date_index ON finance_transactions(user_id,day);
    ''')
    for row in list(db.execute('SELECT id FROM users')):
        seed(db,row['id'])


def seed(db,user_id):
    db.execute('INSERT OR IGNORE INTO finance_settings(user_id) VALUES (?)',(user_id,))
    db.executemany('INSERT OR IGNORE INTO finance_categories VALUES (?,?,?,?,?,?,0)',
                   [(user_id,*category) for category in PRESETS])


def money(data,key,signed=False,zero=True):
    value=data.get(key)
    minimum=-100_000_000_000 if signed else 0 if zero else 1
    if type(value) is not int or not minimum<=value<=100_000_000_000:
        raise ValueError('Сумма должна быть целым числом копеек в допустимом диапазоне.')
    return value


def identifier(value):
    if not isinstance(value,str) or not re.fullmatch(r'[a-zA-Z0-9_-]{1,100}',value):
        raise ValueError('Неверный идентификатор записи.')
    return value


def settings(db,user_id,data):
    opening=money(data,'openingBalanceKopecks',signed=True)
    budget=money(data,'monthlyBudgetKopecks')
    db.execute('UPDATE finance_settings SET opening_balance=?,monthly_budget=? WHERE user_id=?',(opening,budget,user_id))


def category(db,user_id,data):
    category_id=identifier(data.get('id'))
    name=data.get('name');kind=data.get('kind');emoji=data.get('emoji');color=data.get('color')
    if not isinstance(name,str) or not name.strip() or len(name.strip())>40:
        raise ValueError('Название категории: от 1 до 40 символов.')
    if kind not in ('income','expense'):
        raise ValueError('Укажи доход или расход.')
    if not isinstance(emoji,str) or not 1<=len(emoji)<=32 or not isinstance(color,str) or not re.fullmatch(r'#[0-9a-fA-F]{6}',color):
        raise ValueError('Неверный значок или цвет категории.')
    old=db.execute('SELECT * FROM finance_categories WHERE user_id=? AND id=?',(user_id,category_id)).fetchone()
    if old:
        if (old['name'],old['kind'],old['emoji'],old['color'])!=(name.strip(),kind,emoji,color):
            raise ValueError('Категория уже существует с другими данными.')
        return
    db.execute('INSERT INTO finance_categories VALUES (?,?,?,?,?,?,0)',(user_id,category_id,name.strip(),kind,emoji,color))


def budget(db,user_id,category_id,data):
    amount=money(data,'budgetKopecks')
    row=db.execute('SELECT kind FROM finance_categories WHERE user_id=? AND id=?',(user_id,category_id)).fetchone()
    if not row:
        return False
    if row['kind']!='expense':
        raise ValueError('Лимит можно поставить только на расходы.')
    db.execute('UPDATE finance_categories SET budget=? WHERE user_id=? AND id=?',(amount,user_id,category_id))
    return True


def transaction(db,user_id,data,today,editing_id=None):
    entry_id=identifier(editing_id or data.get('id'))
    day=data.get('day')
    if not isinstance(day,str) or not re.fullmatch(r'\d{4}-\d{2}-\d{2}',day) or date.fromisoformat(day).isoformat()!=day or day>today:
        raise ValueError('Укажи существующую дату не позднее сегодняшней.')
    amount=money(data,'amountKopecks',zero=False)
    category_id=identifier(data.get('categoryId'))
    row=db.execute('SELECT kind FROM finance_categories WHERE user_id=? AND id=?',(user_id,category_id)).fetchone()
    if not row:
        raise ValueError('Выбери свою категорию.')
    if data.get('kind')!=row['kind']:
        raise ValueError('Тип операции не совпадает с категорией.')
    note=data.get('note','')
    if not isinstance(note,str) or len(note)>120:
        raise ValueError('Комментарий не должен превышать 120 символов.')
    old=db.execute('SELECT * FROM finance_transactions WHERE user_id=? AND id=?',(user_id,entry_id)).fetchone()
    if editing_id:
        if not old:return False
        db.execute('UPDATE finance_transactions SET day=?,category_id=?,amount=?,note=? WHERE user_id=? AND id=?',
                   (day,category_id,amount,note.strip(),user_id,entry_id))
    elif old:
        if (old['day'],old['category_id'],old['amount'],old['note'])!=(day,category_id,amount,note.strip()):
            raise ValueError('Операция уже сохранена. Обнови список перед изменением.')
    else:
        if db.execute('SELECT COUNT(*) FROM finance_transactions WHERE user_id=?',(user_id,)).fetchone()[0]>=10000:
            raise ValueError('В профиле достигнут лимит в 10 000 операций.')
        db.execute('INSERT INTO finance_transactions VALUES (?,?,?,?,?,?,?)',
                   (user_id,entry_id,day,category_id,amount,note.strip(),datetime.now(timezone.utc).isoformat()))
    return True


def remove(db,user_id,entry_id):
    return db.execute('DELETE FROM finance_transactions WHERE user_id=? AND id=?',(user_id,entry_id)).rowcount>0


def state(db,user_id):
    settings=db.execute('SELECT * FROM finance_settings WHERE user_id=?',(user_id,)).fetchone()
    categories=[dict(id=row['id'],name=row['name'],kind=row['kind'],emoji=row['emoji'],color=row['color'],budgetKopecks=row['budget'])
                for row in db.execute('SELECT * FROM finance_categories WHERE user_id=? ORDER BY rowid',(user_id,))]
    transactions=[dict(id=row['id'],day=row['day'],categoryId=row['category_id'],kind=row['kind'],amountKopecks=row['amount'],note=row['note'])
                  for row in db.execute('''SELECT t.*,c.kind FROM finance_transactions t JOIN finance_categories c
                                           ON c.user_id=t.user_id AND c.id=t.category_id
                                           WHERE t.user_id=? ORDER BY t.day DESC,t.created_at DESC,t.id''',(user_id,))]
    income=sum(row['amountKopecks'] for row in transactions if row['kind']=='income')
    expenses=sum(row['amountKopecks'] for row in transactions if row['kind']=='expense')
    opening=settings['opening_balance'] if settings else 0
    return dict(currency='RUB',openingBalanceKopecks=opening,monthlyBudgetKopecks=settings['monthly_budget'] if settings else 0,
                categories=categories,transactions=transactions,balanceKopecks=opening+income-expenses)
