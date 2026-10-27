import unittest
from datetime import date, timedelta
from test_server import ServerFixture
from backend.app.services import hydration
from backend.app.core.validation import today


class WaterTests(ServerFixture):
    def configure(self, goal=1750):
        return self.request('/api/water/settings','PUT',{'heightCm':175,'weightKg':70,'goalMl':goal,'adult':True})

    def add(self, entry_id='glass-1', amount=250):
        return self.request('/api/water/entries','POST',{'id':entry_id,'amountMl':amount})

    def test_settings_entries_undo_and_idempotent_retry(self):
        self.assertIsNone(self.request()[1]['water']['profile'])
        self.assertEqual(self.add()[0],400)
        self.assertEqual(self.configure(500)[0],200)
        self.assertEqual(self.add()[1]['water']['totalMl'],250)
        self.assertEqual(self.add()[1]['water']['totalMl'],250)
        self.assertEqual(self.add('glass-2')[1]['water']['totalMl'],500)
        self.assertEqual(self.request()[1]['water']['summary']['goalDays'],1)
        self.request('/api/water/entries/glass-2','DELETE',{})
        self.assertEqual(self.request()[1]['water']['totalMl'],250)
        self.assertEqual(self.request()[1]['water']['summary']['goalDays'],0)
        self.stop_server();self.start_server()
        self.assertEqual(self.request()[1]['water']['totalMl'],250)

    def test_water_profile_and_entries_are_private(self):
        self.configure();self.add()
        owner=self.token
        self.request('/api/auth/register','POST',{'email':'other@example.com','name':'Other','password':'other-password'})
        self.assertIsNone(self.request()[1]['water']['profile'])
        self.assertEqual(self.request('/api/water/entries/glass-1','DELETE',{})[0],404)
        self.configure();self.add()
        self.token=owner
        self.assertEqual(self.request()[1]['water']['totalMl'],250)

    def test_previous_day_goals_do_not_change_with_new_settings(self):
        user=self.request()[1]['user']['id']
        yesterday=(date.fromisoformat(today())-timedelta(days=1)).isoformat()
        with self.server.store.connect() as db:
            hydration.settings(db,user,{'heightCm':175,'weightKg':70,'goalMl':500,'adult':True},yesterday)
            hydration.add(db,user,{'id':'yesterday','amountMl':500},yesterday)
        result=self.configure(2000)[1]['water']
        self.assertEqual(result['totalMl'],0)
        self.assertEqual(result['goalMl'],2000)
        self.assertEqual(result['history'][0],{'day':yesterday,'totalMl':500,'goalMl':500})
        self.assertEqual(result['summary']['goalDays'],1)

    def test_invalid_amounts_settings_and_conflicting_retries_are_rejected(self):
        self.assertEqual(self.request('/api/water/settings','PUT',{'heightCm':175,'weightKg':70,'goalMl':1750,'adult':False})[0],400)
        self.configure()
        for value in [True,-250,0,0.5,999999,'250']:
            self.assertEqual(self.add(amount=value)[0],400)
        self.add()
        self.assertEqual(self.add(amount=500)[0],400)
        self.assertEqual(self.request()[1]['water']['totalMl'],250)


if __name__=='__main__':unittest.main()
