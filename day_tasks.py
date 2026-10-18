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
        CREATE TABLE IF NOT EXISTS day_task_items (
            user_id TEXT NOT NULL,task_id TEXT NOT NULL,id TEXT NOT NULL,title TEXT NOT NULL,
            done INTEGER NOT NULL,position INTEGER NOT NULL,PRIMARY KEY(user_id,task_id,id),
            FOREIGN KEY(user_id,task_id) REFERENCES day_tasks(user_id,id) ON DELETE CASCADE);
    ''')


def dispatch(db,user_id,parts,method,data):
    if len(parts)==5 and parts[:2]==['api','tasks'] and parts[3]=='items' and method=='PATCH':
        if type(data.get('done')) is not bool:raise ValueError('Проверь статус подзадачи.')
        changed=db.execute('UPDATE day_task_items SET done=? WHERE user_id=? AND task_id=? AND id=?',(int(data['done']),user_id,parts[2],parts[4])).rowcount
        if changed and not data['done']:db.execute('UPDATE day_tasks SET done=0 WHERE user_id=? AND id=?',(user_id,parts[2]))
        return bool(changed)
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
    items=data.get('checklist')
    if items is not None:
        if not isinstance(items,list) or len(items)>100:raise ValueError('В чеклисте может быть до 100 пунктов.')
        cleaned=[];identifiers=set()
        for item in items:
            if not isinstance(item,dict):raise ValueError('Проверь пункты чеклиста.')
            item_id=finance.identifier(item.get('id'));item_title=text(item,'title',120)
            if item_id in identifiers or type(item.get('done')) is not bool:raise ValueError('Проверь статусы и уникальность подзадач.')
            identifiers.add(item_id);cleaned.append(dict(id=item_id,title=item_title,done=item['done']))
        items=cleaned
    values=(title,note,day,clock,priority,int(done))
    if method=='PATCH':db.execute('UPDATE day_tasks SET title=?,note=?,day=?,time=?,priority=?,done=? WHERE user_id=? AND id=?',(*values,user_id,identifier))
    elif old:
        if tuple(old[k] for k in ('title','note','day','time','priority','done'))!=values:raise ValueError('Эта задача уже сохранена с другими данными.')
    else:db.execute('INSERT INTO day_tasks VALUES (?,?,?,?,?,?,?,?,?)',(user_id,identifier,*values,datetime.now(timezone.utc).isoformat()))
    if items is not None:
        if method=='POST' and old:
            saved=[dict(id=r['id'],title=r['title'],done=bool(r['done'])) for r in db.execute('SELECT * FROM day_task_items WHERE user_id=? AND task_id=? ORDER BY position',(user_id,identifier))]
            if saved!=items:raise ValueError('Этот чеклист уже сохранён с другими данными.')
        else:
            db.execute('DELETE FROM day_task_items WHERE user_id=? AND task_id=?',(user_id,identifier))
            db.executemany('INSERT INTO day_task_items VALUES (?,?,?,?,?,?)',[(user_id,identifier,item['id'],item['title'],int(item['done']),i) for i,item in enumerate(items)])
    if done:db.execute('UPDATE day_task_items SET done=1 WHERE user_id=? AND task_id=?',(user_id,identifier))
    return True


def state(db,user_id):
    items={}
    for r in db.execute('SELECT * FROM day_task_items WHERE user_id=? ORDER BY task_id,position',(user_id,)):
        items.setdefault(r['task_id'],[]).append(dict(id=r['id'],title=r['title'],done=bool(r['done'])))
    return [dict(id=r['id'],title=r['title'],note=r['note'],day=r['day'],time=r['time'],priority=r['priority'],done=bool(r['done']),checklist=items.get(r['id'],[])) for r in db.execute('SELECT * FROM day_tasks WHERE user_id=? ORDER BY done,day,time,created_at,id',(user_id,))]
