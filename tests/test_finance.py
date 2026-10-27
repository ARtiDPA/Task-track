import unittest
from test_server import ServerFixture
from backend.app.core.validation import today


class FinanceTests(ServerFixture):
    def add(self,entry_id='expense',amount=1050,kind='expense',category='groceries',day=None):
        return self.request('/api/finance/transactions','POST',dict(id=entry_id,kind=kind,categoryId=category,day=day or today(),amountKopecks=amount,note='Test'))

    def test_exact_balance_edit_delete_and_persistence(self):
        self.request('/api/finance/settings','PUT',dict(openingBalanceKopecks=10000,monthlyBudgetKopecks=50000))
        self.add('income',20000,'income','salary')
        self.add(amount=1029)
        self.assertEqual(self.request()[1]['finance']['balanceKopecks'],28971)
        self.add(amount=1029)
        self.assertEqual(len(self.request()[1]['finance']['transactions']),2)
        self.request('/api/finance/transactions/expense','PATCH',dict(kind='expense',categoryId='groceries',day=today(),amountKopecks=1099,note='Edited'))
        self.assertEqual(self.request()[1]['finance']['balanceKopecks'],28901)
        self.stop_server();self.start_server()
        self.assertEqual(self.request()[1]['finance']['balanceKopecks'],28901)
        self.request('/api/finance/transactions/expense','DELETE',{})
        self.assertEqual(self.request()[1]['finance']['balanceKopecks'],30000)

    def test_custom_categories_and_limits(self):
        data=dict(id='pets',name='Кот',kind='expense',emoji='🐕',color='#82b69c')
        self.assertEqual(self.request('/api/finance/categories','POST',data)[0],200)
        self.assertEqual(self.request('/api/finance/categories/pets/budget','PUT',dict(budgetKopecks=500000))[0],200)
        self.add(category='pets')
        category=next(c for c in self.request()[1]['finance']['categories'] if c['id']=='pets')
        self.assertEqual(category['budgetKopecks'],500000)
        self.assertEqual(self.request('/api/finance/categories/salary/budget','PUT',dict(budgetKopecks=1))[0],400)

    def test_other_profile_cannot_read_or_change_money(self):
        self.add()
        first=self.token
        self.request('/api/auth/register','POST',dict(email='other@example.com',name='Other',password='other-password'))
        self.assertEqual(self.request()[1]['finance']['transactions'],[])
        self.assertEqual(self.request('/api/finance/transactions/expense','DELETE',{})[0],404)
        self.add(amount=500)
        self.assertEqual(self.request()[1]['finance']['balanceKopecks'],-500)
        self.token=first
        self.assertEqual(self.request()[1]['finance']['balanceKopecks'],-1050)

    def test_invalid_money_dates_and_category_kind(self):
        for value in [True,0,-1,10.5,'100',100000000001]:
            self.assertEqual(self.add(amount=value)[0],400)
        self.assertEqual(self.add(day='2999-01-01')[0],400)
        self.assertEqual(self.add(day='2026-02-31')[0],400)
        self.assertEqual(self.add(kind='income',category='groceries')[0],400)
        self.assertEqual(self.request()[1]['finance']['transactions'],[])


if __name__=='__main__':unittest.main()
