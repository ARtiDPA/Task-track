"""Server-clock focus timer. Only active intervals count; pauses do not."""
import time
from datetime import datetime, timedelta, timezone
import finance
from organizer import text

TZ=timezone(timedelta(hours=3))


def now_ms():return time.time_ns()//1_000_000


def initialize(db):
    db.executescript('''
        CREATE TABLE IF NOT EXISTS focus_settings (
            user_id TEXT PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
            goal_minutes INTEGER NOT NULL,auto_pause INTEGER NOT NULL);
        CREATE TABLE IF NOT EXISTS focus_sessions (
            user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,id TEXT NOT NULL,
            title TEXT NOT NULL,target_ms INTEGER NOT NULL,status TEXT NOT NULL,
            started_ms INTEGER NOT NULL,run_started_ms INTEGER,elapsed_ms INTEGER NOT NULL,
            finished_ms INTEGER,distractions INTEGER NOT NULL,PRIMARY KEY(user_id,id));
        CREATE UNIQUE INDEX IF NOT EXISTS focus_one_active ON focus_sessions(user_id) WHERE status IN ('running','paused');
        CREATE TABLE IF NOT EXISTS focus_segments (
            id INTEGER PRIMARY KEY,user_id TEXT NOT NULL,session_id TEXT NOT NULL,
            start_ms INTEGER NOT NULL,end_ms INTEGER NOT NULL,
            FOREIGN KEY(user_id,session_id) REFERENCES focus_sessions(user_id,id) ON DELETE CASCADE);
        CREATE INDEX IF NOT EXISTS focus_segments_user ON focus_segments(user_id,start_ms);
    ''')


def session(db,user_id,identifier):return db.execute('SELECT * FROM focus_sessions WHERE user_id=? AND id=?',(user_id,identifier)).fetchone()


def settle(db,row,clock):
    elapsed=row['elapsed_ms']
    if row['status']=='running':
        start=row['run_started_ms'];end=max(start,min(clock,start+row['target_ms']-elapsed))
        if end>start:
            db.execute('INSERT INTO focus_segments(user_id,session_id,start_ms,end_ms) VALUES (?,?,?,?)',(row['user_id'],row['id'],start,end))
            elapsed+=end-start
    return elapsed


def reconcile(db,user_id,clock):
    row=db.execute("SELECT * FROM focus_sessions WHERE user_id=? AND status='running'",(user_id,)).fetchone()
    if row and clock>=row['run_started_ms']+row['target_ms']-row['elapsed_ms']:
        finished=row['run_started_ms']+row['target_ms']-row['elapsed_ms']
        settle(db,row,finished)
        db.execute("UPDATE focus_sessions SET status='completed',elapsed_ms=target_ms,run_started_ms=NULL,finished_ms=? WHERE user_id=? AND id=?",(finished,user_id,row['id']))


def dispatch(db,user_id,parts,method,data):
    clock=now_ms();reconcile(db,user_id,clock)
    if parts==['api','focus','settings'] and method=='PUT':
        goal=data.get('goalMinutes');auto=data.get('autoPause')
        if type(goal) is not int or not 5<=goal<=720 or type(auto) is not bool:raise ValueError('Цель — от 5 до 720 минут. Проверь настройку паузы.')
        db.execute('INSERT INTO focus_settings VALUES (?,?,?) ON CONFLICT(user_id) DO UPDATE SET goal_minutes=excluded.goal_minutes,auto_pause=excluded.auto_pause',(user_id,goal,int(auto)));return True
    if parts[:3]!=['api','focus','sessions']:raise ValueError('Неизвестное действие.')
    if method=='POST' and len(parts)==3:
        identifier=finance.identifier(data.get('id'));title=text(data,'title',120);minutes=data.get('minutes')
        if type(minutes) is not int or not 1<=minutes<=180:raise ValueError('Длительность сессии — от 1 до 180 минут.')
        old=session(db,user_id,identifier)
        if old:
            if old['title']!=title or old['target_ms']!=minutes*60000:raise ValueError('Эта сессия уже сохранена.')
            return True
        if db.execute("SELECT 1 FROM focus_sessions WHERE user_id=? AND status IN ('running','paused')",(user_id,)).fetchone():raise ValueError('Сначала заверши или отмени текущую сессию.')
        db.execute('INSERT INTO focus_sessions VALUES (?,?,?,?,?,?,?,?,?,?)',(user_id,identifier,title,minutes*60000,'running',clock,clock,0,None,0));return True
    if len(parts) not in (4,5):raise ValueError('Неизвестное действие.')
    row=session(db,user_id,parts[3])
    if not row:return False
    if len(parts)==4 and method=='DELETE':
        if row['status']!='completed':raise ValueError('Для активной сессии используй отмену.')
        db.execute('DELETE FROM focus_sessions WHERE user_id=? AND id=?',(user_id,row['id']));return True
    if method!='POST' or len(parts)!=5:raise ValueError('Неизвестное действие.')
    action=parts[4]
    if action not in ('pause','resume','distract','finish','cancel'):raise ValueError('Неизвестное действие.')
    if action=='cancel':
        if row['status']=='completed':raise ValueError('Сессия уже завершена. Её можно удалить из истории.')
        db.execute('DELETE FROM focus_sessions WHERE user_id=? AND id=?',(user_id,row['id']));return True
    if row['status']=='completed':return True
    if action=='resume':
        if row['status']=='paused':db.execute("UPDATE focus_sessions SET status='running',run_started_ms=? WHERE user_id=? AND id=?",(clock,user_id,row['id']))
    elif action in ('pause','distract'):
        if row['status']=='running':
            elapsed=settle(db,row,clock)
            db.execute("UPDATE focus_sessions SET status='paused',run_started_ms=NULL,elapsed_ms=?,distractions=distractions+? WHERE user_id=? AND id=?",(elapsed,int(action=='distract'),user_id,row['id']))
    elif action=='finish':
        elapsed=settle(db,row,clock)
        db.execute("UPDATE focus_sessions SET status='completed',run_started_ms=NULL,elapsed_ms=?,finished_ms=? WHERE user_id=? AND id=?",(elapsed,clock,user_id,row['id']))
    return True


def state(db,user_id):
    # /api/state may arrive after the browser was closed; settle elapsed sessions once.
    if not db.in_transaction:db.execute('BEGIN IMMEDIATE')
    clock=now_ms();reconcile(db,user_id,clock)
    rows=db.execute('SELECT * FROM focus_sessions WHERE user_id=? ORDER BY started_ms DESC,id',(user_id,)).fetchall()
    active=next((r for r in rows if r['status']!='completed'),None)
    intervals=[(r['start_ms'],r['end_ms']) for r in db.execute('SELECT start_ms,end_ms FROM focus_segments WHERE user_id=?',(user_id,))]
    if active and active['status']=='running':intervals.append((active['run_started_ms'],max(active['run_started_ms'],min(clock,active['run_started_ms']+active['target_ms']-active['elapsed_ms']))))
    daily={}
    for start,end in intervals:
        while start<end:
            current=datetime.fromtimestamp(start/1000,TZ);day=current.date().isoformat()
            midnight=datetime.combine(current.date()+timedelta(days=1),datetime.min.time(),TZ)
            boundary=min(end,int(midnight.timestamp()*1000));daily[day]=daily.get(day,0)+boundary-start;start=boundary
    def packed(r):
        elapsed=r['elapsed_ms']+(max(0,clock-r['run_started_ms']) if r['status']=='running' else 0)
        return dict(id=r['id'],title=r['title'],targetMs=r['target_ms'],elapsedMs=min(r['target_ms'],elapsed),status=r['status'],startedMs=r['started_ms'],finishedMs=r['finished_ms'],distractions=r['distractions'])
    settings=db.execute('SELECT * FROM focus_settings WHERE user_id=?',(user_id,)).fetchone()
    return dict(serverNowMs=clock,active=packed(active) if active else None,history=[packed(r) for r in rows if r['status']=='completed'][:100],daily=[dict(day=d,milliseconds=ms) for d,ms in sorted(daily.items())],totalMs=sum(daily.values()),sessionCount=sum(r['status']=='completed' and r['elapsed_ms']>0 for r in rows),bestSessionMs=max((r['elapsed_ms'] for r in rows if r['status']=='completed'),default=0),distractions=sum(r['distractions'] for r in rows),settings=dict(goalMinutes=settings['goal_minutes'] if settings else 120,autoPause=bool(settings['auto_pause']) if settings else True))
