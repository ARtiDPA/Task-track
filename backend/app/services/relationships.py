"""Private relationship notebook, ideas and dates. Amounts are integer kopecks."""
from datetime import datetime, timezone, time, timedelta
import re
from urllib.parse import urlsplit
from backend.app.services import finance
from backend.app.services.organizer import text, day_value, linked_id

KINDS=('note','gift','date','milestone','care','memory')


def initialize(db,today=None):
    today=today or datetime.now(timezone(timedelta(hours=3))).date().isoformat()
    db.executescript('''
        CREATE TABLE IF NOT EXISTS relationship_profiles (
            user_id TEXT PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
            partner_name TEXT NOT NULL DEFAULT '', together_day TEXT NOT NULL DEFAULT ''
        );
        CREATE TABLE IF NOT EXISTS relationship_entries (
            user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            id TEXT NOT NULL,kind TEXT NOT NULL,title TEXT NOT NULL,body TEXT NOT NULL,
            category TEXT NOT NULL,price INTEGER,location TEXT NOT NULL,url TEXT NOT NULL,
            day TEXT NOT NULL,time TEXT NOT NULL,done INTEGER NOT NULL,pinned INTEGER NOT NULL,yearly INTEGER NOT NULL,
            created_at TEXT NOT NULL,PRIMARY KEY(user_id,id)
        );
        CREATE INDEX IF NOT EXISTS relationship_entries_profile ON relationship_entries(user_id,kind,day);
        CREATE TABLE IF NOT EXISTS relationship_activity (
            user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,id TEXT NOT NULL,
            entry_id TEXT,kind TEXT NOT NULL,title TEXT NOT NULL,day TEXT NOT NULL,created_at TEXT NOT NULL,
            PRIMARY KEY(user_id,id),UNIQUE(user_id,entry_id)
        );
        CREATE INDEX IF NOT EXISTS relationship_activity_day ON relationship_activity(user_id,kind,day);
    ''')
    if 'completed_day' not in [r['name'] for r in db.execute('PRAGMA table_info(relationship_entries)')]:
        db.execute("ALTER TABLE relationship_entries ADD COLUMN completed_day TEXT NOT NULL DEFAULT ''")
    # Preserve old completion marks using the recorded day, never a future planned date.
    for r in db.execute("SELECT * FROM relationship_entries WHERE done=1 AND kind IN ('gift','date','care') AND completed_day=''").fetchall():
        actual=r['day'] if r['day'] and r['day']<=today else min(r['created_at'][:10],today)
        db.execute('UPDATE relationship_entries SET completed_day=? WHERE user_id=? AND id=?',(actual,r['user_id'],r['id']))
        db.execute('INSERT OR IGNORE INTO relationship_activity VALUES (?,?,?,?,?,?,?)',(r['user_id'],linked_id('rel',r['id']),r['id'],r['kind'],r['title'],actual,r['created_at']))


def dispatch(db,user_id,parts,method,data,today=None):
    today=today or datetime.now(timezone(timedelta(hours=3))).date().isoformat()
    if parts[:3]==['api','relationships','activity']:
        if method=='POST' and len(parts)==3:
            identifier=finance.identifier(data.get('id'));kind=data.get('kind');day=day_value(data.get('day'));title=text(data,'title',100)
            if kind not in ('gift','date','care') or day>today:raise ValueError('Укажи тип события и фактическую дату не позже сегодня.')
            old=db.execute('SELECT * FROM relationship_activity WHERE user_id=? AND id=?',(user_id,identifier)).fetchone()
            if old:
                if old['entry_id'] or (old['kind'],old['title'],old['day'])!=(kind,title,day):raise ValueError('Эта отметка уже сохранена.')
            else:db.execute('INSERT INTO relationship_activity VALUES (?,?,?,?,?,?,?)',(user_id,identifier,None,kind,title,day,datetime.now(timezone.utc).isoformat()))
            return True
        if method=='DELETE' and len(parts)==4:
            old=db.execute('SELECT * FROM relationship_activity WHERE user_id=? AND id=?',(user_id,parts[3])).fetchone()
            if not old:return False
            if old['entry_id']:db.execute("UPDATE relationship_entries SET done=0,completed_day='' WHERE user_id=? AND id=?",(user_id,old['entry_id']))
            db.execute('DELETE FROM relationship_activity WHERE user_id=? AND id=?',(user_id,parts[3]));return True
        raise ValueError('Неизвестное действие.')
    if method=='PUT' and parts==['api','relationships','profile']:
        name=text(data,'partnerName',60,True);day=day_value(data.get('togetherDay'),True)
        db.execute('INSERT INTO relationship_profiles VALUES (?,?,?) ON CONFLICT(user_id) DO UPDATE SET partner_name=excluded.partner_name,together_day=excluded.together_day',(user_id,name,day))
        return True
    if len(parts) not in (3,4) or parts[:3]!=['api','relationships','entries']:raise ValueError('Неизвестное действие.')
    identifier=finance.identifier(parts[3] if len(parts)==4 else data.get('id'))
    old=db.execute('SELECT * FROM relationship_entries WHERE user_id=? AND id=?',(user_id,identifier)).fetchone()
    if len(parts)==4 and not old:return False
    if method=='DELETE' and len(parts)==4:
        db.execute('DELETE FROM relationship_activity WHERE user_id=? AND entry_id=?',(user_id,identifier))
        db.execute('DELETE FROM relationship_entries WHERE user_id=? AND id=?',(user_id,identifier));return True
    if (method,len(parts)) not in [('POST',3),('PATCH',4)]:raise ValueError('Неизвестное действие.')
    kind=data.get('kind');title=text(data,'title',100);body=text(data,'body',6000,True)
    category=text(data,'category',60,True);location=text(data,'location',180,True);url=text(data,'url',1000,True)
    day=day_value(data.get('day'),True)
    clock=text(data,'time',5,True)
    if clock:
        if not day or not re.fullmatch(r'\d{2}:\d{2}',clock):raise ValueError('Для времени укажи дату и формат ЧЧ:ММ.')
        time.fromisoformat(clock)
    if kind not in KINDS:raise ValueError('Выбери тип записи.')
    if old and kind!=old['kind']:raise ValueError('Тип сохранённой записи менять нельзя.')
    flags=[]
    for key in ('done','pinned','yearly'):
        if type(data.get(key)) is not bool:raise ValueError('Проверь статус записи.')
        flags.append(int(data[key]))
    if data['yearly'] and kind!='milestone':raise ValueError('Ежегодный повтор доступен для важных дат.')
    if kind in ('milestone','memory') and not day:raise ValueError('Укажи дату этого события.')
    price=data.get('priceKopecks')
    if price is not None:
        price=finance.money(data,'priceKopecks')
        if kind not in ('gift','date'):raise ValueError('Бюджет доступен для подарков и свиданий.')
    if url:
        try:parsed=urlsplit(url)
        except ValueError:raise ValueError('Проверь ссылку.')
        if parsed.scheme not in ('http','https') or not parsed.hostname or any(c.isspace() or ord(c)<32 for c in url):raise ValueError('Ссылка должна начинаться с https:// или http://.')
    tracked=kind in ('gift','date','care') and data['done']
    completed=day_value(data.get('completedDay') or (old['completed_day'] if old and old['done'] else today)) if tracked else ''
    if tracked and completed>today:raise ValueError('Фактическая дата события не может быть в будущем.')
    values=(kind,title,body,category,price,location,url,day,clock,*flags,completed)
    if method=='PATCH':
        db.execute('UPDATE relationship_entries SET kind=?,title=?,body=?,category=?,price=?,location=?,url=?,day=?,time=?,done=?,pinned=?,yearly=?,completed_day=? WHERE user_id=? AND id=?',(*values,user_id,identifier))
    elif old:
        if tuple(old[key] for key in ('kind','title','body','category','price','location','url','day','time','done','pinned','yearly','completed_day'))!=values:raise ValueError('Эта запись уже сохранена с другими данными.')
    else:
        db.execute('INSERT INTO relationship_entries (user_id,id,kind,title,body,category,price,location,url,day,time,done,pinned,yearly,completed_day,created_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',(user_id,identifier,*values,datetime.now(timezone.utc).isoformat()))
    if tracked:
        db.execute('INSERT INTO relationship_activity VALUES (?,?,?,?,?,?,?) ON CONFLICT(user_id,id) DO UPDATE SET title=excluded.title,day=excluded.day',(user_id,linked_id('rel',identifier),identifier,kind,title,completed,datetime.now(timezone.utc).isoformat()))
    else:db.execute('DELETE FROM relationship_activity WHERE user_id=? AND entry_id=?',(user_id,identifier))
    return True


def state(db,user_id):
    profile=db.execute('SELECT * FROM relationship_profiles WHERE user_id=?',(user_id,)).fetchone()
    entries=[dict(id=r['id'],kind=r['kind'],title=r['title'],body=r['body'],category=r['category'],priceKopecks=r['price'],location=r['location'],url=r['url'],day=r['day'],time=r['time'],done=bool(r['done']),pinned=bool(r['pinned']),yearly=bool(r['yearly']),completedDay=r['completed_day']) for r in db.execute('SELECT * FROM relationship_entries WHERE user_id=? ORDER BY pinned DESC,created_at DESC,id',(user_id,))]
    activities=[dict(id=r['id'],entryId=r['entry_id'],kind=r['kind'],title=r['title'],day=r['day']) for r in db.execute('SELECT * FROM relationship_activity WHERE user_id=? ORDER BY day DESC,created_at DESC,id',(user_id,))]
    return dict(partnerName=profile['partner_name'] if profile else '',togetherDay=profile['together_day'] if profile else '',entries=entries,activities=activities)
