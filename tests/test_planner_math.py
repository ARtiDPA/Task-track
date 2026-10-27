import unittest
from pathlib import Path
from playwright.sync_api import sync_playwright


class PlannerMathTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.playwright=sync_playwright().start();cls.browser=cls.playwright.chromium.launch(channel='msedge',headless=True)
        cls.page=cls.browser.new_page();cls.page.add_script_tag(path=str(Path(__file__).resolve().parents[1] / 'frontend' / 'static' / 'js' / 'schedule.js'));cls.page.add_script_tag(path=str(Path(__file__).resolve().parents[1] / 'frontend' / 'static' / 'js' / 'planner-math.js'))

    @classmethod
    def tearDownClass(cls):cls.browser.close();cls.playwright.stop()

    def calculate(self,finance,organizer,options=None):
        return self.page.evaluate("([f,o,opts])=>RitmoPlanner.calculate(f,o,'2026-10-18','2026-10-24',opts)",[finance,organizer,options or {}])

    def test_daily_budget_respects_dates_and_reserved_money(self):
        finance=dict(openingBalanceKopecks=100000,transactions=[])
        organizer=dict(reservedKopecks=20000,plans=[dict(id='rent',name='Rent',kind='expense',amountKopecks=30000,day='2026-10-20',status='pending'),dict(id='salary',name='Salary',kind='income',amountKopecks=50000,day='2026-10-22',status='pending')])
        result=self.calculate(finance,organizer)
        self.assertEqual(result['free'],80000);self.assertEqual(result['ending'],100000)
        self.assertEqual(result['daily'],12500);self.assertEqual(result['week'],87500)
        self.assertEqual(self.calculate(finance,organizer,{'includeIncome':False})['daily'],7142)

    def test_positive_final_balance_does_not_hide_an_earlier_shortfall(self):
        organizer=dict(plans=[dict(id='rent',name='Rent',kind='expense',amountKopecks=20000,day='2026-10-18',status='pending'),dict(id='salary',name='Salary',kind='income',amountKopecks=40000,day='2026-10-19',status='pending')])
        result=self.calculate(dict(openingBalanceKopecks=10000,transactions=[]),organizer)
        self.assertEqual(result['ending'],30000);self.assertEqual(result['daily'],0);self.assertEqual(result['firstShortfall'],'2026-10-18')

    def test_posted_plans_and_closed_debts_are_not_counted_twice(self):
        organizer=dict(plans=[dict(id='paid',name='Paid',kind='expense',amountKopecks=5000,day='2026-10-18',status='posted')],debts=[dict(id='closed',name='Debt',remainingKopecks=0,dueDay='2026-10-19',direction='owe',paymentKopecks=0)])
        result=self.calculate(dict(openingBalanceKopecks=10000,transactions=[dict(kind='expense',amountKopecks=5000)]),organizer)
        self.assertEqual(result['ending'],5000);self.assertEqual(result['expenses'],0)

    def test_debt_only_contributes_the_next_payment_and_overdue_is_due_now(self):
        organizer=dict(debts=[dict(id='debt',name='Debt',remainingKopecks=90000,paymentKopecks=10000,dueDay='2026-10-10',direction='owe')])
        result=self.calculate(dict(openingBalanceKopecks=100000,transactions=[]),organizer)
        self.assertEqual(result['expenses'],10000);self.assertEqual(result['overdue'],1)
        self.assertEqual(result['series'][0]['balance'],90000)

    def test_monthly_debt_expands_all_instalments_and_caps_at_remaining(self):
        debt=dict(id='credit',name='Credit',direction='owe',remainingKopecks=25000,paymentKopecks=5000,monthlyDay=31,monthlyPaymentKopecks=10000,dueDay='2027-01-31')
        rows=self.page.evaluate("d=>RitmoSchedule.debtOccurrences(d,'2027-06-30')",debt)
        self.assertEqual(rows,[dict(day='2027-01-31',amount=5000),dict(day='2027-02-28',amount=10000),dict(day='2027-03-31',amount=10000)])
        result=self.page.evaluate("d=>RitmoPlanner.calculate({openingBalanceKopecks:100000},{debts:[d]},'2027-01-01','2027-04-30')",debt)
        self.assertEqual(result['expenses'],25000)
        self.assertEqual(len(result['items']),3)
        debt['dueDay']='2028-01-31'
        rows=self.page.evaluate("d=>RitmoSchedule.debtOccurrences(d,'2028-03-31','2028-02-01')",debt)
        self.assertEqual([r['day'] for r in rows],['2028-02-29','2028-03-31'])

    def forecast(self,interval='month',start='2027-01-31',today='2027-01-01',**changes):
        pot=dict(targetKopecks=27000,balanceKopecks=2000,contributionKopecks=10000,contributionInterval=interval,contributionStartDay=start)
        return self.page.evaluate('([p,t])=>RitmoSchedule.savingsForecast(p,t)',[{**pot,**changes},today])

    def test_savings_forecast_monthly_weekly_daily_and_final_partial(self):
        f=self.forecast()
        self.assertEqual((f['day'],f['count'],f['lastContribution']),('2027-03-31',3,5000))
        self.assertEqual([p['day'] for p in f['points']],['2027-01-01','2027-01-31','2027-02-28','2027-03-31'])
        self.assertEqual(self.forecast('week','2027-01-01')['day'],'2027-01-15')
        self.assertEqual(self.forecast('day','2027-01-01')['day'],'2027-01-03')
        self.assertEqual(self.forecast(today='2027-02-01')['day'],'2027-04-30')
        self.assertEqual(self.forecast(today='2027-02-28')['firstDay'],'2027-02-28')
        self.assertEqual(self.forecast(contributionKopecks=0)['status'],'unconfigured')
        self.assertEqual(self.forecast(balanceKopecks=27000)['status'],'reached')
        self.assertEqual(self.forecast(targetKopecks=0)['status'],'reserve')
        self.assertEqual(self.forecast(targetKopecks=100000000000,contributionKopecks=1)['status'],'distant')


if __name__=='__main__':unittest.main()
