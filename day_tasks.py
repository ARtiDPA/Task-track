"""One shared task store for the day planner and calendar."""
from datetime import datetime, timezone, time
import re
import finance
from organizer import text, day_value


def initialize(db):
    db.executescript('''CREATE TABLE IF NOT EXISTS day_tasks (
        user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,id TEXT NOT NULL,
        title TEXT NOT NULL,note TEXT NOT NULL,day TEXT NOT NULL,time TEXT NOT NULL,
        priority TEXT NOT NULL,done INTEGER NOT NULL,created_at TEXT NOT NULL,
        PRIMARY KEY(user_id,id));
        CREATE INDEX IF NOT EXISTS day_tasks_day ON day_tasks(user_id,day);
    ''')


def dispatch(db,user_id,parts,method,data):
    if len(parts) not in (2,3) or parts[:2]!=['api','tasks']:raise ValueError('Неизвестное действие.')
    identifier=finance.identifier(parts[2] if len(parts)==3 else data.get('id'))
    old=db.execute('SELECT * FROM day_tasks WHERE user_id=? AND id=?',(user_id,identifier)).fetchone()
    if len(parts)==3 and not old:return False
    if method=='DELETE' and len(parts)==3:
        db.execute('DELETE FROM day_tasks WHERE user_id=? AND id=?',(user_id,identifier));return True
    if (method,len(parts)) not in [('POST',2),('PATCH',3)]:raise ValueError('Неизвестное действие.')
    title=text(data,'title',120);note=text(data,'note',3000,True);day=day_value(data.get('day'),True);clock=text(data,'time',5,True)
    if clock:
        if not day or not re.fullmatch(r'\d{2}:\d{2}',clock):raise ValueError('Для времени укажи дату и формат ЧЧ:ММ.')
        time.fromisoformat(clock)
    priority=data.get('priority','normal');done=data.get('done',False)
    if priority not in ('low','normal','high') or type(done) is not bool:raise ValueError('Проверь приоритет и статус задачи.')
    values=(title,note,day,clock,priority,int(done))
    if method=='PATCH':db.execute('UPDATE day_tasks SET title=?,note=?,day=?,time=?,priority=?,done=? WHERE user_id=? AND id=?',(*values,user_id,identifier))
    elif old:
        if tuple(old[k] for k in ('title','note','day','time','priority','done'))!=values:raise ValueError('Эта задача уже сохранена с другими данными.')
    else:db.execute('INSERT INTO day_tasks VALUES (?,?,?,?,?,?,?,?,?)',(user_id,identifier,*values,datetime.now(timezone.utc).isoformat()))
    return True


def state(db,user_id):
    return [dict(id=r['id'],title=r['title'],note=r['note'],day=r['day'],time=r['time'],priority=r['priority'],done=bool(r['done'])) for r in db.execute('SELECT * FROM day_tasks WHERE user_id=? ORDER BY done,day,time,created_at,id',(user_id,))]
