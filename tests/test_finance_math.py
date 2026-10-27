import unittest
from pathlib import Path
from playwright.sync_api import sync_playwright


class FinanceMathTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.playwright=sync_playwright().start();cls.browser=cls.playwright.chromium.launch(channel='msedge',headless=True)
        cls.page=cls.browser.new_page();cls.page.add_script_tag(path=str(Path(__file__).resolve().parents[1] / 'frontend' / 'static' / 'js' / 'finance-math.js'))

    @classmethod
    def tearDownClass(cls):cls.browser.close();cls.playwright.stop()

    def test_decimal_input_is_exact_and_bad_values_are_rejected(self):
        result=self.page.evaluate("""()=>['0,10','0.20','1 250,50','-100,01'].map(value=>RitmoFinanceMath.parseAmount(value,true))""")
        self.assertEqual(result,[10,20,125050,-10001])
        for value in ['1.234','1e5','NaN','12,3,4','-10']:
            self.assertTrue(self.page.evaluate("value=>{try{RitmoFinanceMath.parseAmount(value);return false;}catch{return true;}}",value))

    def test_balance_uses_full_history_but_month_totals_do_not(self):
        data=dict(openingBalanceKopecks=10000,monthlyBudgetKopecks=5000,categories=[],transactions=[
            dict(day='2026-09-20',kind='income',amountKopecks=20000),dict(day='2026-10-10',kind='expense',amountKopecks=3000)])
        result=self.page.evaluate("data=>RitmoFinanceMath.summarize(data,'2026-10','2026-10-18')",data)
        self.assertEqual(result['balance'],27000);self.assertEqual(result['income'],0);self.assertEqual(result['expenses'],3000)
        self.assertEqual(result['series'][0]['balance'],30000);self.assertEqual(result['remaining'],2000)
        self.assertEqual(result['dailyAvailable'],142)

    def test_negative_balance_does_not_produce_positive_daily_allowance(self):
        data=dict(openingBalanceKopecks=0,monthlyBudgetKopecks=50000,categories=[],transactions=[dict(day='2026-10-01',kind='expense',amountKopecks=1000)])
        result=self.page.evaluate("data=>RitmoFinanceMath.summarize(data,'2026-10','2026-10-18')",data)
        self.assertEqual(result['dailyAvailable'],0)
        result=self.page.evaluate("data=>RitmoFinanceMath.summarize(data,'2026-09','2026-10-18')",data)
        self.assertEqual(result['daysLeft'],0)


if __name__=='__main__':unittest.main()
