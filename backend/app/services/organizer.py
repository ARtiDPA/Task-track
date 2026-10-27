"""Savings, debts, scheduled transactions and events; profile-scoped and atomic."""
import hashlib
import re
import calendar
from datetime import date, datetime, timezone, time
from backend.app.services import finance


def initialize(db):
    db.executescript('''
        CREATE TABLE IF NOT EXISTS savings_pots (
            user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,id TEXT NOT NULL,
            name TEXT NOT NULL,kind TEXT NOT NULL,location TEXT NOT NULL,location_name TEXT NOT NULL,
            target INTEGER NOT NULL,balance INTEGER NOT NULL,status TEXT NOT NULL DEFAULT 'active',
            purchase_amount INTEGER NOT NULL DEFAULT 0,balance_before_purchase INTEGER NOT NULL DEFAULT 0,
            transaction_id TEXT,created_at TEXT NOT NULL,PRIMARY KEY(user_id,id)
        );
        CREATE TABLE IF NOT EXISTS savings_moves (
            user_id TEXT NOT NULL,id TEXT NOT NULL,pot_id TEXT NOT NULL,amount INTEGER NOT NULL,created_at TEXT NOT NULL,
            PRIMARY KEY(user_id,id),FOREIGN KEY(user_id,pot_id) REFERENCES savings_pots(user_id,id) ON DELETE CASCADE
        );
        CREATE TABLE IF NOT EXISTS debts (
            user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,id TEXT NOT NULL,
            name TEXT NOT NULL,party TEXT NOT NULL,direction TEXT NOT NULL,amount INTEGER NOT NULL,
            due_day TEXT NOT NULL,payment_amount INTEGER NOT NULL,note TEXT NOT NULL,created_at TEXT NOT NULL,
            PRIMARY KEY(user_id,id)
        );
        CREATE TABLE IF NOT EXISTS debt_payments (
            user_id TEXT NOT NULL,id TEXT NOT NULL,debt_id TEXT NOT NULL,amount INTEGER NOT NULL,
            day TEXT NOT NULL,transaction_id TEXT,created_at TEXT NOT NULL,previous_due TEXT NOT NULL DEFAULT '',previous_payment INTEGER NOT NULL DEFAULT 0,PRIMARY KEY(user_id,id),
            FOREIGN KEY(user_id,debt_id) REFERENCES debts(user_id,id) ON DELETE CASCADE
        );
        CREATE TABLE IF NOT EXISTS finance_plans (
            user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,id TEXT NOT NULL,
            name TEXT NOT NULL,kind TEXT NOT NULL,category_id TEXT NOT NULL,amount INTEGER NOT NULL,
            day TEXT NOT NULL,status TEXT NOT NULL DEFAULT 'pending',transaction_id TEXT,actual_day TEXT,
            PRIMARY KEY(user_id,id),FOREIGN KEY(user_id,category_id) REFERENCES finance_categories(user_id,id)
        );
        CREATE TABLE IF NOT EXISTS calendar_events (
            user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,id TEXT NOT NULL,
            title TEXT NOT NULL,day TEXT NOT NULL,time TEXT NOT NULL,note TEXT NOT NULL,
            PRIMARY KEY(user_id,id)
        );
    ''')
    if 'previous_due' not in [row['name'] for row in db.execute('PRAGMA table_info(debt_payments)')]:
        db.execute("ALTER TABLE debt_payments ADD COLUMN previous_due TEXT NOT NULL DEFAULT ''")
    if 'previous_payment' not in [row['name'] for row in db.execute('PRAGMA table_info(debt_payments)')]:
        db.execute('ALTER TABLE debt_payments ADD COLUMN previous_payment INTEGER NOT NULL DEFAULT 0')
    for column in ('monthly_day','monthly_amount'):
        if column not in [row['name'] for row in db.execute('PRAGMA table_info(debts)')]:
            db.execute(f'ALTER TABLE debts ADD COLUMN {column} INTEGER NOT NULL DEFAULT 0')
    for column,definition in [('contribution_amount','INTEGER NOT NULL DEFAULT 0'),('contribution_interval',"TEXT NOT NULL DEFAULT 'month'"),('contribution_start',"TEXT NOT NULL DEFAULT ''")]:
        if column not in [row['name'] for row in db.execute('PRAGMA table_info(savings_pots)')]:
            db.execute(f'ALTER TABLE savings_pots ADD COLUMN {column} {definition}')


def monthly_date(value, anchor, months=0):
    current=date.fromisoformat(value)
    year,month=divmod(current.year*12+current.month-1+months,12)
    if not 1900<=year<=2100:raise ValueError('График выходит за допустимый диапазон дат.')
    return date(year,month+1,min(anchor,calendar.monthrange(year,month+1)[1])).isoformat()


def now():return datetime.now(timezone.utc).isoformat()


def text(data,key,limit=80,optional=False):
    value=data.get(key,'')
    if not isinstance(value,str) or len(value.strip())>limit or (not optional and not value.strip()):
        raise ValueError(f'Проверь поле «{key}».')
    return value.strip()


def day_value(value,optional=False):
    if optional and value in ('',None):return ''
    if not isinstance(value,str) or not re.fullmatch(r'\d{4}-\d{2}-\d{2}',value):raise ValueError('Укажи дату.')
    if not '1900-01-01'<=value<='2100-12-31' or date.fromisoformat(value).isoformat()!=value:raise ValueError('Проверь дату.')
    return value


def row_for(db,table,user_id,entry_id):
    return db.execute(f'SELECT * FROM {table} WHERE user_id=? AND id=?',(user_id,entry_id)).fetchone()


def reserved(db,user_id):
    return db.execute("SELECT COALESCE(SUM(balance),0) FROM savings_pots WHERE user_id=? AND status='active'",(user_id,)).fetchone()[0]


def available(db,user_id):return finance.state(db,user_id)['balanceKopecks']-reserved(db,user_id)


def linked_id(source,entity):return source+'-'+hashlib.sha256(entity.encode()).hexdigest()


def record(db,user_id,entry_id,kind,category,amount,day,note,source,entity,today):
    finance.transaction(db,user_id,dict(id=entry_id,kind=kind,categoryId=category,amountKopecks=amount,day=day,note=note[:120]),today)
    db.execute('INSERT INTO finance_links VALUES (?,?,?,?)',(user_id,entry_id,source,entity))


def unrecord(db,user_id,entry_id):
    if entry_id:db.execute('DELETE FROM finance_transactions WHERE user_id=? AND id=?',(user_id,entry_id))


def save_pot(db,user_id,data,entry_id=None):
    identifier=finance.identifier(entry_id or data.get('id'));old=row_for(db,'savings_pots',user_id,identifier)
    name=text(data,'name');kind=data.get('kind');location=data.get('location');place=text(data,'locationName',60,True)
    if kind not in ('purchase','reserve') or location not in ('cash','bank','other'):raise ValueError('Выбери тип копилки и место хранения.')
    target=finance.money(data,'targetKopecks',zero=kind=='reserve')
    contribution=finance.money({'amount':data.get('contributionKopecks',old['contribution_amount'] if old else 0)},'amount')
    interval=data.get('contributionInterval',old['contribution_interval'] if old else 'month')
    start=day_value(data.get('contributionStartDay',old['contribution_start'] if old else ''),True)
    if interval not in ('day','week','month'):raise ValueError('Выбери частоту взносов: день, неделя или месяц.')
    if contribution and not start:raise ValueError('Укажи дату первого регулярного взноса.')
    if not contribution:start=''
    if entry_id:
        if not old:return False
        if old['status']!='active':raise ValueError('Сначала отмени покупку, чтобы изменить копилку.')
        db.execute('UPDATE savings_pots SET name=?,kind=?,location=?,location_name=?,target=?,contribution_amount=?,contribution_interval=?,contribution_start=? WHERE user_id=? AND id=?',(name,kind,location,place,target,contribution,interval,start,user_id,identifier))
    else:
        balance=finance.money(data,'balanceKopecks')
        if old:
            if (old['name'],old['kind'],old['location'],old['location_name'],old['target'],old['balance'],old['contribution_amount'],old['contribution_interval'],old['contribution_start'])!=(name,kind,location,place,target,balance,contribution,interval,start):raise ValueError('Эта копилка уже сохранена.')
            return True
        if balance>max(0,available(db,user_id)):raise ValueError('Недостаточно свободных денег. Проверь начальный остаток в финансах.')
        db.execute('INSERT INTO savings_pots VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',(user_id,identifier,name,kind,location,place,target,balance,'active',0,0,None,now(),contribution,interval,start))
    return True


def move_pot(db,user_id,entry_id,data):
    pot=row_for(db,'savings_pots',user_id,entry_id)
    if not pot:return False
    if pot['status']!='active':raise ValueError('Покупка уже завершена.')
    move_id=finance.identifier(data.get('id'));amount=finance.money(data,'amountKopecks',zero=False)
    if data.get('direction') not in ('deposit','withdraw'):raise ValueError('Выбери пополнение или возврат.')
    amount=amount if data['direction']=='deposit' else -amount
    old=row_for(db,'savings_moves',user_id,move_id)
    if old:
        if old['pot_id']!=entry_id or old['amount']!=amount:raise ValueError('Это перемещение уже сохранено.')
        return True
    if amount>max(0,available(db,user_id)):raise ValueError('Недостаточно свободных денег для пополнения.')
    if pot['balance']+amount<0:raise ValueError('В копилке нет такой суммы.')
    db.execute('INSERT INTO savings_moves VALUES (?,?,?,?,?)',(user_id,move_id,entry_id,amount,now()))
    db.execute('UPDATE savings_pots SET balance=balance+? WHERE user_id=? AND id=?',(amount,user_id,entry_id))
    return True


def buy_pot(db,user_id,entry_id,data,today,undo=False):
    pot=row_for(db,'savings_pots',user_id,entry_id)
    if not pot:return False
    if undo:
        if pot['status']!='bought':return True
        unrecord(db,user_id,pot['transaction_id'])
        db.execute("UPDATE savings_pots SET status='active',balance=balance_before_purchase,purchase_amount=0,balance_before_purchase=0,transaction_id=NULL WHERE user_id=? AND id=?",(user_id,entry_id))
    else:
        if pot['status']=='bought':return True
        if pot['kind']!='purchase' or pot['balance']<pot['target']:raise ValueError('Для покупки сначала накопи целевую сумму.')
        amount=finance.money(data,'amountKopecks',zero=False)
        if amount>pot['balance']:raise ValueError('Стоимость больше суммы в копилке.')
        txn=linked_id('savings',entry_id)
        record(db,user_id,txn,'expense','shopping',amount,today,'Покупка: '+pot['name'],'savings',entry_id,today)
        db.execute("UPDATE savings_pots SET status='bought',balance_before_purchase=balance,balance=0,purchase_amount=?,transaction_id=? WHERE user_id=? AND id=?",(amount,txn,user_id,entry_id))
    return True


def save_debt(db,user_id,data,entry_id=None):
    identifier=finance.identifier(entry_id or data.get('id'));old=row_for(db,'debts',user_id,identifier)
    name=text(data,'name');party=text(data,'party',80,True);direction=data.get('direction');amount=finance.money(data,'amountKopecks',zero=False)
    due=day_value(data.get('dueDay'),True);payment=finance.money(data,'paymentKopecks');note=text(data,'note',300,True)
    monthly_day=data.get('monthlyDay',old['monthly_day'] if old else 0)
    monthly_amount=finance.money({'amount':data.get('monthlyPaymentKopecks',old['monthly_amount'] if old else 0)},'amount')
    if type(monthly_day) is not int or not 0<=monthly_day<=31:raise ValueError('День ежемесячного платежа — от 1 до 31.')
    if monthly_day:
        if not due or not monthly_amount or not payment:raise ValueError('Для ежемесячного графика укажи дату, ближайший и регулярный платёж.')
        if monthly_date(due,monthly_day)!=due:raise ValueError('Дата первого платежа должна совпадать с выбранным числом месяца (или последним днём короткого месяца).')
    else:monthly_amount=0
    if direction not in ('owe','owed'):raise ValueError('Выбери, кто кому должен.')
    paid=db.execute('SELECT COALESCE(SUM(amount),0) FROM debt_payments WHERE user_id=? AND debt_id=?',(user_id,identifier)).fetchone()[0]
    if paid>amount:raise ValueError('Сумма долга не может быть меньше уже погашенной суммы.')
    if payment>amount-paid:raise ValueError('Ближайший платёж больше остатка долга.')
    if entry_id:
        if not old:return False
        if paid and direction!=old['direction']:raise ValueError('Нельзя менять направление долга с платежами.')
        db.execute('UPDATE debts SET name=?,party=?,direction=?,amount=?,due_day=?,payment_amount=?,note=?,monthly_day=?,monthly_amount=? WHERE user_id=? AND id=?',(name,party,direction,amount,due,payment,note,monthly_day,monthly_amount,user_id,identifier))
    elif old:
        if (old['name'],old['party'],old['direction'],old['amount'],old['due_day'],old['payment_amount'],old['note'],old['monthly_day'],old['monthly_amount'])!=(name,party,direction,amount,due,payment,note,monthly_day,monthly_amount):raise ValueError('Долг уже сохранён.')
    else:db.execute('INSERT INTO debts VALUES (?,?,?,?,?,?,?,?,?,?,?,?)',(user_id,identifier,name,party,direction,amount,due,payment,note,now(),monthly_day,monthly_amount))
    return True


def pay_debt(db,user_id,entry_id,data,today):
    debt=row_for(db,'debts',user_id,entry_id)
    if not debt:return False
    payment_id=finance.identifier(data.get('id'));amount=finance.money(data,'amountKopecks',zero=False)
    day=day_value(data.get('day'))
    if day>today:raise ValueError('Фактический платёж не может быть в будущем.')
    if type(data.get('recordTransaction')) is not bool:raise ValueError('Укажи, нужно ли учитывать платёж в финансах.')
    old=row_for(db,'debt_payments',user_id,payment_id)
    if old:
        if old['debt_id']!=entry_id or old['amount']!=amount or old['day']!=day or bool(old['transaction_id'])!=data['recordTransaction']:raise ValueError('Платёж уже записан с другими данными.')
        return True
    paid=db.execute('SELECT COALESCE(SUM(amount),0) FROM debt_payments WHERE user_id=? AND debt_id=?',(user_id,entry_id)).fetchone()[0]
    if amount>debt['amount']-paid:raise ValueError('Платёж больше остатка долга.')
    next_due=day_value(data.get('nextDueDay'),True)
    if debt['monthly_day'] and next_due and monthly_date(next_due,debt['monthly_day'])!=next_due:
        raise ValueError('Следующая дата должна совпадать с днём ежемесячного платежа.')
    txn=None
    if data['recordTransaction']:
        txn=linked_id('debt',payment_id);kind='expense' if debt['direction']=='owe' else 'income'
        record(db,user_id,txn,kind,'other-expense' if kind=='expense' else 'other-income',amount,day,'Долг: '+debt['name'],'debt',entry_id,today)
    db.execute('INSERT INTO debt_payments VALUES (?,?,?,?,?,?,?,?,?)',(user_id,payment_id,entry_id,amount,day,txn,now(),debt['due_day'],debt['payment_amount']))
    remaining=debt['amount']-paid-amount
    scheduled=debt['payment_amount']
    if not remaining:
        next_due='';next_amount=0
    elif debt['monthly_day']:
        regular=debt['monthly_amount'];current_due=debt['due_day'];current_amount=scheduled or regular
        excess=amount
        if excess>=current_amount:
            excess-=current_amount
            skipped,excess=divmod(excess,regular)
            current_due=monthly_date(current_due,debt['monthly_day'],1+skipped)
            if current_due>'2100-12-31':raise ValueError('Следующий платёж выходит за допустимый диапазон дат.')
            current_amount=regular
        next_due=next_due or current_due
        next_amount=min(current_amount-excess,remaining)
    elif next_due:
        next_amount=min(scheduled,remaining)
    elif scheduled and amount<scheduled:
        next_due=debt['due_day'];next_amount=min(scheduled-amount,remaining)
    elif scheduled:
        # The scheduled instalment has been fulfilled; don't invent a new due date.
        next_due='';next_amount=min(scheduled,remaining)
    else:
        next_due=debt['due_day'] if remaining else '';next_amount=0
    db.execute('UPDATE debts SET due_day=?,payment_amount=? WHERE user_id=? AND id=?',(next_due,next_amount,user_id,entry_id))
    return True


def save_plan(db,user_id,data,entry_id=None):
    identifier=finance.identifier(entry_id or data.get('id'));old=row_for(db,'finance_plans',user_id,identifier)
    name=text(data,'name');kind=data.get('kind');category=finance.identifier(data.get('categoryId'));amount=finance.money(data,'amountKopecks',zero=False);day=day_value(data.get('day'))
    cat=row_for(db,'finance_categories',user_id,category)
    if not cat or cat['kind']!=kind:raise ValueError('Выбери категорию нужного типа.')
    if entry_id:
        if not old:return False
        if old['status']!='pending':raise ValueError('Сначала верни план в ожидание.')
        db.execute('UPDATE finance_plans SET name=?,kind=?,category_id=?,amount=?,day=? WHERE user_id=? AND id=?',(name,kind,category,amount,day,user_id,identifier))
    elif old:
        if (old['name'],old['kind'],old['category_id'],old['amount'],old['day'])!=(name,kind,category,amount,day):raise ValueError('План уже сохранён.')
    else:db.execute('INSERT INTO finance_plans VALUES (?,?,?,?,?,?,?,?,?,?)',(user_id,identifier,name,kind,category,amount,day,'pending',None,None))
    return True


def plan_action(db,user_id,entry_id,action,data,today):
    plan=row_for(db,'finance_plans',user_id,entry_id)
    if not plan:return False
    if action=='post':
        if plan['status']=='posted':return True
        if plan['status']!='pending':raise ValueError('Сначала восстанови отменённый план.')
        actual=day_value(data.get('actualDay',today))
        if actual>today:raise ValueError('Провести операцию можно только фактической датой.')
        txn=linked_id('plan',entry_id)
        record(db,user_id,txn,plan['kind'],plan['category_id'],plan['amount'],actual,plan['name'],'plan',entry_id,today)
        db.execute("UPDATE finance_plans SET status='posted',transaction_id=?,actual_day=? WHERE user_id=? AND id=?",(txn,actual,user_id,entry_id))
    elif action=='undo':
        unrecord(db,user_id,plan['transaction_id'])
        db.execute("UPDATE finance_plans SET status='pending',transaction_id=NULL,actual_day=NULL WHERE user_id=? AND id=?",(user_id,entry_id))
    elif action=='cancel':
        if plan['status']=='posted':raise ValueError('Сначала отмени проведение операции.')
        db.execute("UPDATE finance_plans SET status='cancelled' WHERE user_id=? AND id=?",(user_id,entry_id))
    else:raise ValueError('Неизвестное действие.')
    return True


def save_event(db,user_id,data,entry_id=None):
    identifier=finance.identifier(entry_id or data.get('id'));old=row_for(db,'calendar_events',user_id,identifier)
    title=text(data,'title');day=day_value(data.get('day'));clock=text(data,'time',5,True);note=text(data,'note',500,True)
    if clock:
        if not re.fullmatch(r'\d{2}:\d{2}',clock):raise ValueError('Проверь время.')
        time.fromisoformat(clock)
    if entry_id:
        if not old:return False
        db.execute('UPDATE calendar_events SET title=?,day=?,time=?,note=? WHERE user_id=? AND id=?',(title,day,clock,note,user_id,identifier))
    elif old:
        if (old['title'],old['day'],old['time'],old['note'])!=(title,day,clock,note):raise ValueError('Событие уже сохранено.')
    else:db.execute('INSERT INTO calendar_events VALUES (?,?,?,?,?,?)',(user_id,identifier,title,day,clock,note))
    return True


def dispatch(db,user_id,parts,method,data,today):
    # Returns False only for a missing profile-owned resource.
    resource=parts[2] if len(parts)>2 else '';entry_id=parts[3] if len(parts)>3 else None;action=parts[4] if len(parts)>4 else None
    if resource=='savings':
        if method=='POST' and len(parts)==3:return save_pot(db,user_id,data)
        if method=='PATCH' and len(parts)==4:return save_pot(db,user_id,data,entry_id)
        if method=='POST' and action=='move' and len(parts)==5:return move_pot(db,user_id,entry_id,data)
        if method=='POST' and action in ('buy','undo-buy') and len(parts)==5:return buy_pot(db,user_id,entry_id,data,today,action=='undo-buy')
        if method=='DELETE' and len(parts)==4:
            row=row_for(db,'savings_pots',user_id,entry_id)
            if not row:return False
            if row['balance'] or row['status']=='bought':raise ValueError('Сначала верни деньги из копилки или отмени покупку.')
            db.execute('DELETE FROM savings_pots WHERE user_id=? AND id=?',(user_id,entry_id));return True
    if resource=='debts':
        if method=='POST' and len(parts)==3:return save_debt(db,user_id,data)
        if method=='PATCH' and len(parts)==4:return save_debt(db,user_id,data,entry_id)
        if method=='POST' and action=='payments' and len(parts)==5:return pay_debt(db,user_id,entry_id,data,today)
        if method=='DELETE' and action=='payments' and len(parts)==6:
            row=row_for(db,'debt_payments',user_id,parts[5])
            if not row or row['debt_id']!=entry_id:return False
            latest=db.execute('SELECT id FROM debt_payments WHERE user_id=? AND debt_id=? ORDER BY created_at DESC,id DESC LIMIT 1',(user_id,entry_id)).fetchone()
            if latest['id']!=row['id'] and row_for(db,'debts',user_id,entry_id)['monthly_day']:
                raise ValueError('Для ежемесячного графика отменяй платежи с последнего: так даты останутся правильными.')
            if latest['id']==row['id']:
                db.execute('UPDATE debts SET due_day=?,payment_amount=? WHERE user_id=? AND id=?',(row['previous_due'],row['previous_payment'],user_id,entry_id))
            unrecord(db,user_id,row['transaction_id']);db.execute('DELETE FROM debt_payments WHERE user_id=? AND id=?',(user_id,parts[5]));return True
        if method=='DELETE' and len(parts)==4:
            if db.execute('SELECT 1 FROM debt_payments WHERE user_id=? AND debt_id=?',(user_id,entry_id)).fetchone():raise ValueError('Долг с платежами остаётся в истории. Можно отменить ошибочные платежи.')
            return db.execute('DELETE FROM debts WHERE user_id=? AND id=?',(user_id,entry_id)).rowcount>0
    if resource=='plans':
        if method=='POST' and len(parts)==3:return save_plan(db,user_id,data)
        if method=='PATCH' and len(parts)==4:return save_plan(db,user_id,data,entry_id)
        if method=='POST' and len(parts)==5:return plan_action(db,user_id,entry_id,action,data,today)
        if method=='DELETE' and len(parts)==4:
            row=row_for(db,'finance_plans',user_id,entry_id)
            if not row:return False
            if row['status']=='posted':raise ValueError('Сначала отмени проведение.')
            db.execute('DELETE FROM finance_plans WHERE user_id=? AND id=?',(user_id,entry_id));return True
    if resource=='events':
        if method=='POST' and len(parts)==3:return save_event(db,user_id,data)
        if method=='PATCH' and len(parts)==4:return save_event(db,user_id,data,entry_id)
        if method=='DELETE' and len(parts)==4:return db.execute('DELETE FROM calendar_events WHERE user_id=? AND id=?',(user_id,entry_id)).rowcount>0
    raise ValueError('Неизвестное действие.')


def state(db,user_id):
    pots=[dict(id=r['id'],name=r['name'],kind=r['kind'],location=r['location'],locationName=r['location_name'],targetKopecks=r['target'],balanceKopecks=r['balance'],status=r['status'],purchaseKopecks=r['purchase_amount'],contributionKopecks=r['contribution_amount'],contributionInterval=r['contribution_interval'],contributionStartDay=r['contribution_start']) for r in db.execute('SELECT * FROM savings_pots WHERE user_id=? ORDER BY created_at,id',(user_id,))]
    debts=[]
    for r in db.execute('SELECT * FROM debts WHERE user_id=? ORDER BY due_day,id',(user_id,)):
        payments=[dict(id=p['id'],amountKopecks=p['amount'],day=p['day'],recorded=bool(p['transaction_id'])) for p in db.execute('SELECT * FROM debt_payments WHERE user_id=? AND debt_id=? ORDER BY created_at DESC,id',(user_id,r['id']))]
        remaining=r['amount']-sum(p['amountKopecks'] for p in payments)
        debts.append(dict(id=r['id'],name=r['name'],party=r['party'],direction=r['direction'],amountKopecks=r['amount'],remainingKopecks=remaining,dueDay=r['due_day'],paymentKopecks=min(r['payment_amount'],remaining),monthlyDay=r['monthly_day'],monthlyPaymentKopecks=r['monthly_amount'],note=r['note'],payments=payments,status='closed' if remaining==0 else 'open'))
    plans=[dict(id=r['id'],name=r['name'],kind=r['kind'],categoryId=r['category_id'],amountKopecks=r['amount'],day=r['day'],status=r['status'],actualDay=r['actual_day']) for r in db.execute('SELECT * FROM finance_plans WHERE user_id=? ORDER BY day,id',(user_id,))]
    events=[dict(id=r['id'],title=r['title'],day=r['day'],time=r['time'],note=r['note']) for r in db.execute('SELECT * FROM calendar_events WHERE user_id=? ORDER BY day,time,id',(user_id,))]
    return dict(savings=pots,debts=debts,plans=plans,events=events,reservedKopecks=reserved(db,user_id))
