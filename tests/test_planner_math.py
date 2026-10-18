import unittest
from pathlib import Path
from playwright.sync_api import sync_playwright


class PlannerMathTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.playwright=sync_playwright().start();cls.browser=cls.playwright.chromium.launch(channel='msedge',headless=True)
        cls.page=cls.browser.new_page();cls.page.add_script_tag(path=str(Path(__file__).resolve().parents[1]/'planner-math.js'))

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


if __name__=='__main__':unittest.main()
