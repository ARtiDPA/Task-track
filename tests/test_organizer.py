import unittest
from test_server import ServerFixture
from server import today


class OrganizerTests(ServerFixture):
    def setUp(self):
        super().setUp()
        self.request('/api/finance/settings','PUT',dict(openingBalanceKopecks=100000,monthlyBudgetKopecks=0))

    def pot(self,kind='purchase',balance=20000):
        return self.request('/api/organizer/savings','POST',dict(id='gift',name='Подарок',kind=kind,location='bank',locationName='Мой банк',targetKopecks=20000,balanceKopecks=balance))

    def debt(self):
        return self.request('/api/organizer/debts','POST',dict(id='credit',name='Рассрочка',party='Банк',direction='owe',amountKopecks=30000,dueDay='2027-01-10',paymentKopecks=10000,note=''))

    def plan(self):
        return self.request('/api/organizer/plans','POST',dict(id='rent',name='Аренда',kind='expense',categoryId='home',amountKopecks=15000,day='2027-01-01'))

    def test_savings_are_reserved_not_spent_and_purchase_is_atomic(self):
        result=self.pot()[1]
        self.assertEqual(result['finance']['balanceKopecks'],100000)
        self.assertEqual(result['finance']['freeBalanceKopecks'],80000)
        result=self.request('/api/organizer/savings/gift/buy','POST',dict(amountKopecks=18000))[1]
        self.assertEqual(result['finance']['balanceKopecks'],82000)
        self.assertEqual(result['finance']['reservedKopecks'],0)
        self.assertEqual(result['organizer']['savings'][0]['status'],'bought')
        self.request('/api/organizer/savings/gift/buy','POST',dict(amountKopecks=18000))
        self.assertEqual(len(self.request()[1]['finance']['transactions']),1)
        txn=result['finance']['transactions'][0]['id']
        self.assertEqual(self.request('/api/finance/transactions/'+txn,'DELETE',{})[0],400)
        result=self.request('/api/organizer/savings/gift/undo-buy','POST',{})[1]
        self.assertEqual(result['finance']['balanceKopecks'],100000)
        self.assertEqual(result['finance']['reservedKopecks'],20000)
        self.assertEqual(result['finance']['transactions'],[])

    def test_savings_moves_are_idempotent_and_cannot_overdraw(self):
        self.pot('reserve',0)
        move=dict(id='move',amountKopecks=50000,direction='deposit')
        self.request('/api/organizer/savings/gift/move','POST',move)
        self.request('/api/organizer/savings/gift/move','POST',move)
        self.assertEqual(self.request()[1]['finance']['reservedKopecks'],50000)
        self.assertEqual(self.request('/api/organizer/savings/gift/move','POST',dict(id='bad',amountKopecks=60000,direction='withdraw'))[0],400)
        self.assertEqual(self.request('/api/organizer/savings/gift/buy','POST',dict(amountKopecks=10000))[0],400)

    def test_debt_payments_close_undo_and_do_not_duplicate(self):
        self.debt()
        payload=dict(id='payment',amountKopecks=30000,day=today(),nextDueDay='',recordTransaction=True)
        result=self.request('/api/organizer/debts/credit/payments','POST',payload)[1]
        self.assertEqual(result['organizer']['debts'][0]['status'],'closed')
        self.assertEqual(result['finance']['balanceKopecks'],70000)
        self.request('/api/organizer/debts/credit/payments','POST',payload)
        self.assertEqual(self.request()[1]['finance']['balanceKopecks'],70000)
        result=self.request('/api/organizer/debts/credit/payments/payment','DELETE',{})[1]
        self.assertEqual(result['organizer']['debts'][0]['remainingKopecks'],30000)
        self.assertEqual(result['finance']['balanceKopecks'],100000)
        payload['recordTransaction']=False
        result=self.request('/api/organizer/debts/credit/payments','POST',payload)[1]
        self.assertEqual(result['finance']['balanceKopecks'],100000)

    def test_plans_only_affect_actual_money_when_posted(self):
        self.plan()
        self.assertEqual(self.request()[1]['finance']['balanceKopecks'],100000)
        self.assertEqual(self.request('/api/organizer/plans/rent/post','POST',dict(actualDay='2027-01-01'))[0],400)
        self.request('/api/organizer/plans/rent/post','POST',dict(actualDay=today()))
        self.request('/api/organizer/plans/rent/post','POST',dict(actualDay=today()))
        result=self.request()[1]
        self.assertEqual(result['finance']['balanceKopecks'],85000)
        self.assertEqual(result['organizer']['plans'][0]['status'],'posted')
        result=self.request('/api/organizer/plans/rent/undo','POST',{})[1]
        self.assertEqual(result['finance']['balanceKopecks'],100000)

    def test_partial_instalments_and_undo_keep_the_schedule_correct(self):
        self.debt()
        payment=dict(id='part',amountKopecks=2000,day=today(),nextDueDay='',recordTransaction=False)
        debt=self.request('/api/organizer/debts/credit/payments','POST',payment)[1]['organizer']['debts'][0]
        self.assertEqual(debt['paymentKopecks'],8000)
        self.assertEqual(debt['dueDay'],'2027-01-10')
        self.request('/api/organizer/debts/credit/payments/part','DELETE',{})
        payment.update(id='complete-instalment',amountKopecks=10000)
        debt=self.request('/api/organizer/debts/credit/payments','POST',payment)[1]['organizer']['debts'][0]
        self.assertEqual(debt['dueDay'],'')
        debt=self.request('/api/organizer/debts/credit/payments/complete-instalment','DELETE',{})[1]['organizer']['debts'][0]
        self.assertEqual(debt['dueDay'],'2027-01-10')
        self.assertEqual(debt['paymentKopecks'],10000)

    def test_calendar_dates_persist_and_all_resources_are_private(self):
        self.pot();self.debt();self.plan()
        event=dict(id='party',title='День рождения',day='2027-01-01',time='18:30',note='Подарок')
        self.assertEqual(self.request('/api/organizer/events','POST',event)[0],200)
        self.stop_server();self.start_server()
        self.assertEqual(self.request()[1]['organizer']['events'][0]['title'],'День рождения')
        self.request('/api/auth/register','POST',dict(email='other@example.com',name='Other',password='other-password'))
        for key in ('savings','debts','plans','events'):self.assertEqual(self.request()[1]['organizer'][key],[])
        for resource,identifier in [('savings','gift'),('debts','credit'),('plans','rent'),('events','party')]:
            self.assertEqual(self.request(f'/api/organizer/{resource}/{identifier}','DELETE',{})[0],404)

    def test_monthly_debt_partial_payments_month_end_and_undo(self):
        payload=dict(id='monthly',name='Credit',party='',direction='owe',amountKopecks=35000,dueDay='2027-01-31',paymentKopecks=10000,monthlyDay=31,monthlyPaymentKopecks=10000,note='')
        self.assertEqual(self.request('/api/organizer/debts','POST',payload)[0],200)
        self.stop_server();self.start_server()
        self.assertEqual(self.request()[1]['organizer']['debts'][0]['monthlyDay'],31)
        pay=dict(id='partial',amountKopecks=3000,day=today(),recordTransaction=False)
        debt=self.request('/api/organizer/debts/monthly/payments','POST',pay)[1]['organizer']['debts'][0]
        self.assertEqual((debt['dueDay'],debt['paymentKopecks']),('2027-01-31',7000))
        pay.update(id='rest',amountKopecks=7000)
        debt=self.request('/api/organizer/debts/monthly/payments','POST',pay)[1]['organizer']['debts'][0]
        self.assertEqual((debt['dueDay'],debt['paymentKopecks']),('2027-02-28',10000))
        pay.update(id='double',amountKopecks=12000)
        debt=self.request('/api/organizer/debts/monthly/payments','POST',pay)[1]['organizer']['debts'][0]
        self.assertEqual((debt['dueDay'],debt['paymentKopecks']),('2027-03-31',8000))
        debt=self.request('/api/organizer/debts/monthly/payments/double','DELETE',{})[1]['organizer']['debts'][0]
        self.assertEqual((debt['dueDay'],debt['paymentKopecks']),('2027-02-28',10000))
        pay.update(id='close',amountKopecks=25000)
        debt=self.request('/api/organizer/debts/monthly/payments','POST',pay)[1]['organizer']['debts'][0]
        self.assertEqual((debt['dueDay'],debt['remainingKopecks']),('',0))

    def test_monthly_schedule_validation(self):
        payload=dict(id='monthly',name='Credit',party='',direction='owe',amountKopecks=30000,dueDay='2027-02-28',paymentKopecks=10000,monthlyDay=31,monthlyPaymentKopecks=10000,note='')
        for field,value in [('monthlyDay',32),('monthlyDay',True),('monthlyPaymentKopecks',0),('dueDay',''),('dueDay','2027-02-27')]:
            self.assertEqual(self.request('/api/organizer/debts','POST',{**payload,field:value})[0],400)
        self.assertEqual(self.request('/api/organizer/debts','POST',payload)[0],200)

    def test_savings_contribution_plan_persists_without_moving_money(self):
        payload=dict(id='goal',name='Trip',kind='purchase',location='bank',locationName='',targetKopecks=500000,balanceKopecks=0,contributionKopecks=50000,contributionInterval='month',contributionStartDay='2027-01-31')
        self.assertEqual(self.request('/api/organizer/savings','POST',payload)[0],200)
        self.stop_server();self.start_server()
        result=self.request()[1];pot=result['organizer']['savings'][0]
        self.assertEqual((pot['contributionKopecks'],pot['contributionInterval'],pot['contributionStartDay']),(50000,'month','2027-01-31'))
        self.assertEqual(result['finance']['balanceKopecks'],100000)
        self.assertEqual(result['finance']['reservedKopecks'],0)
        self.assertEqual(result['finance']['transactions'],[])
        for field,value in [('contributionInterval','year'),('contributionKopecks',-1),('contributionStartDay','2027-02-30'),('contributionStartDay','')]:
            self.assertEqual(self.request('/api/organizer/savings/goal','PATCH',{**payload,field:value})[0],400)
        payload['contributionInterval']='week'
        self.assertEqual(self.request('/api/organizer/savings/goal','PATCH',payload)[0],200)

    def test_old_database_is_migrated_without_losing_pots_or_debts(self):
        self.pot();self.debt();self.stop_server()
        with self.server.store.connect() as db:
            for col in ('monthly_day','monthly_amount'):db.execute('ALTER TABLE debts DROP COLUMN '+col)
            for col in ('contribution_amount','contribution_interval','contribution_start'):db.execute('ALTER TABLE savings_pots DROP COLUMN '+col)
        self.start_server()
        result=self.request()[1]
        self.assertEqual(result['organizer']['debts'][0]['amountKopecks'],30000)
        self.assertEqual(result['organizer']['debts'][0]['monthlyDay'],0)
        self.assertEqual(result['organizer']['savings'][0]['balanceKopecks'],20000)
        self.assertEqual(result['organizer']['savings'][0]['contributionKopecks'],0)

    def test_calendar_events_can_be_edited_and_deleted_with_date_validation(self):
        event=dict(id='meeting',title='Встреча',day='2027-02-28',time='18:30',note='Адрес')
        self.request('/api/organizer/events','POST',event)
        event['title']='Новая встреча'
        self.assertEqual(self.request('/api/organizer/events/meeting','PATCH',event)[0],200)
        self.assertEqual(self.request()[1]['organizer']['events'][0]['title'],'Новая встреча')
        event['day']='2027-02-30'
        self.assertEqual(self.request('/api/organizer/events/meeting','PATCH',event)[0],400)
        event.update(day='2027-02-28',time='29:00')
        self.assertEqual(self.request('/api/organizer/events/meeting','PATCH',event)[0],400)
        self.assertEqual(self.request('/api/organizer/events/meeting','DELETE',{})[0],200)
        self.assertEqual(self.request()[1]['organizer']['events'],[])


if __name__=='__main__':unittest.main()
