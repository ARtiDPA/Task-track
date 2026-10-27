"""Profile-private personal wishes; wish prices never change the finance ledger."""
from datetime import datetime, timezone
from urllib.parse import urlsplit
from backend.app.services import finance
from backend.app.services.organizer import text


def initialize(db):
    db.executescript('''CREATE TABLE IF NOT EXISTS wish_items (
        user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,id TEXT NOT NULL,
        title TEXT NOT NULL,note TEXT NOT NULL,category TEXT NOT NULL,price INTEGER,url TEXT NOT NULL,
        priority TEXT NOT NULL,status TEXT NOT NULL,acquired_day TEXT NOT NULL,created_at TEXT NOT NULL,
        PRIMARY KEY(user_id,id));''')


def dispatch(db,user_id,parts,method,data,today):
    if len(parts) not in (2,3):raise ValueError('Неизвестное действие.')
    identifier=finance.identifier(parts[2] if len(parts)==3 else data.get('id'))
    old=db.execute('SELECT * FROM wish_items WHERE user_id=? AND id=?',(user_id,identifier)).fetchone()
    if len(parts)==3 and not old:return False
    if method=='DELETE' and len(parts)==3:
        db.execute('DELETE FROM wish_items WHERE user_id=? AND id=?',(user_id,identifier));return True
    if (method,len(parts)) not in [('POST',2),('PATCH',3)]:raise ValueError('Неизвестное действие.')
    title=text(data,'title',100);note=text(data,'note',3000,True);category=text(data,'category',60,True);url=text(data,'url',1000,True)
    price=finance.money(data,'priceKopecks') if data.get('priceKopecks') is not None else None
    priority=data.get('priority','normal');status=data.get('status','wanted')
    if priority not in ('low','normal','high') or status not in ('wanted','acquired','archived'):raise ValueError('Проверь статус и приоритет желания.')
    if url:
        try:parsed=urlsplit(url)
        except ValueError:raise ValueError('Проверь ссылку.')
        if parsed.scheme not in ('https','http') or not parsed.hostname or any(c.isspace() or ord(c)<32 for c in url):raise ValueError('Укажи обычную ссылку https:// или http://.')
    acquired=(old['acquired_day'] if old and old['status']=='acquired' else today) if status=='acquired' else ''
    values=(title,note,category,price,url,priority,status,acquired)
    if method=='PATCH':db.execute('UPDATE wish_items SET title=?,note=?,category=?,price=?,url=?,priority=?,status=?,acquired_day=? WHERE user_id=? AND id=?',(*values,user_id,identifier))
    elif old:
        if tuple(old[k] for k in ('title','note','category','price','url','priority','status','acquired_day'))!=values:raise ValueError('Это желание уже сохранено с другими данными.')
    else:db.execute('INSERT INTO wish_items VALUES (?,?,?,?,?,?,?,?,?,?,?)',(user_id,identifier,*values,datetime.now(timezone.utc).isoformat()))
    return True


def state(db,user_id):
    return [dict(id=r['id'],title=r['title'],note=r['note'],category=r['category'],priceKopecks=r['price'],url=r['url'],priority=r['priority'],status=r['status'],acquiredDay=r['acquired_day']) for r in db.execute('SELECT * FROM wish_items WHERE user_id=? ORDER BY created_at DESC,id',(user_id,))]
