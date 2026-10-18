import unittest
from test_server import ServerFixture


class RelationshipTests(ServerFixture):
    def entry(self,kind='note',**values):
        return dict(id='entry',kind=kind,title='Любит пионы',body='Белые и розовые',category='Цветы',priceKopecks=None,location='',url='',day='',time='',done=False,pinned=False,yearly=False,**values)

    def test_notes_crud_and_restart_preserve_all_details(self):
        payload=self.entry()
        result=self.request('/api/relationships/entries','POST',payload)
        self.assertEqual(result[0],200)
        self.assertEqual(result[1]['relationships']['entries'][0]['body'],'Белые и розовые')
        payload.update(body='Ещё любит ромашки\nРазмер кольца 16',pinned=True)
        self.assertEqual(self.request('/api/relationships/entries/entry','PATCH',payload)[0],200)
        self.stop_server();self.start_server()
        record=self.request()[1]['relationships']['entries'][0]
        self.assertTrue(record['pinned']);self.assertEqual(record['body'],payload['body'])
        self.assertEqual(self.request('/api/relationships/entries/entry','DELETE',{})[0],200)
        self.assertEqual(self.request()[1]['relationships']['entries'],[])

    def test_gifts_dates_and_plans_do_not_change_actual_finances(self):
        for kind in ('gift','date','care','memory','milestone'):
            payload=self.entry(kind);payload.update(id=kind,title=kind,day='2027-02-28',time='19:30',yearly=kind=='milestone')
            if kind in ('gift','date'):payload.update(priceKopecks=125050,url='https://example.com/idea',location='В центре')
            self.assertEqual(self.request('/api/relationships/entries','POST',payload)[0],200)
        result=self.request()[1]
        self.assertEqual(len(result['relationships']['entries']),5)
        self.assertEqual(result['finance']['transactions'],[])
        self.assertEqual(result['organizer']['events'],[])
        self.assertEqual(result['organizer']['plans'],[])
        entry=next(e for e in result['relationships']['entries'] if e['kind']=='gift')
        entry['done']=True
        self.assertEqual(self.request('/api/relationships/entries/gift','PATCH',entry)[0],200)
        self.assertEqual(self.request()[1]['finance']['balanceKopecks'],0)

    def test_profile_and_entries_are_private(self):
        self.request('/api/relationships/profile','PUT',dict(partnerName='Маша',togetherDay='2024-06-15'))
        self.request('/api/relationships/entries','POST',self.entry())
        self.stop_server();self.start_server()
        self.assertEqual(self.request()[1]['relationships']['partnerName'],'Маша')
        self.request('/api/auth/register','POST',dict(email='second@example.com',name='Second',password='second-password'))
        self.assertEqual(self.request()[1]['relationships'],dict(partnerName='',togetherDay='',entries=[],activities=[]))
        self.assertEqual(self.request('/api/relationships/entries/entry','PATCH',self.entry())[0],404)
        self.assertEqual(self.request('/api/relationships/entries/entry','DELETE',{})[0],404)
        self.assertEqual(self.request('/api/relationships/entries','POST',self.entry())[0],200)

    def test_validation_rejects_unsafe_links_bad_dates_and_money(self):
        payload=self.entry('gift')
        for field,value in [('priceKopecks',-1),('priceKopecks',1.5),('priceKopecks',True),('url','javascript:alert(1)'),('url','https://'),('url','https://example.com/ bad'),('day','2027-02-30'),('time','25:00'),('yearly',True),('done','yes'),('body','x'*6001),('kind','invalid')]:
            self.assertEqual(self.request('/api/relationships/entries','POST',{**payload,field:value})[0],400,(field,value))
        for kind in ('memory','milestone'):
            self.assertEqual(self.request('/api/relationships/entries','POST',self.entry(kind))[0],400)
        self.assertEqual(self.request('/api/relationships/profile','PUT',dict(partnerName='A',togetherDay='2026-13-01'))[0],400)
        self.assertEqual(self.request()[1]['relationships']['entries'],[])

    def test_creation_is_idempotent_and_free_price_differs_from_unknown(self):
        payload=self.entry('gift');payload['priceKopecks']=0
        self.request('/api/relationships/entries','POST',payload)
        self.request('/api/relationships/entries','POST',payload)
        self.assertEqual(len(self.request()[1]['relationships']['entries']),1)
        self.assertEqual(self.request()[1]['relationships']['entries'][0]['priceKopecks'],0)
        self.assertEqual(self.request('/api/relationships/entries','POST',{**payload,'title':'Changed'})[0],400)
        self.assertEqual(self.request('/api/relationships/entries/entry','PATCH',{**payload,'kind':'date'})[0],400)

    def test_activity_history_is_idempotent_sorted_and_private(self):
        payload=dict(id='moment',kind='gift',title='Flowers',day='2026-01-10')
        self.assertEqual(self.request('/api/relationships/activity','POST',payload)[0],200)
        self.request('/api/relationships/activity','POST',payload)
        self.request('/api/relationships/activity','POST',{**payload,'id':'newer','day':'2026-01-20'})
        self.stop_server();self.start_server()
        items=self.request()[1]['relationships']['activities']
        self.assertEqual([a['day'] for a in items],['2026-01-20','2026-01-10'])
        self.request('/api/relationships/activity/newer','DELETE',{})
        self.assertEqual(self.request()[1]['relationships']['activities'][0]['day'],'2026-01-10')
        self.assertEqual(self.request('/api/relationships/activity','POST',{**payload,'id':'future','day':'2099-01-01'})[0],400)
        self.request('/api/auth/register','POST',dict(email='other@example.com',name='Other',password='other-password'))
        self.assertEqual(self.request()[1]['relationships']['activities'],[])
        self.assertEqual(self.request('/api/relationships/activity/moment','DELETE',{})[0],404)

    def test_actual_completion_date_is_separate_from_plan_and_undo_is_consistent(self):
        from server import today
        payload=self.entry('date');payload.update(day='2027-01-15')
        self.request('/api/relationships/entries','POST',payload)
        self.assertEqual(self.request()[1]['relationships']['activities'],[])
        payload.update(done=True,completedDay='2026-01-10')
        result=self.request('/api/relationships/entries/entry','PATCH',payload)[1]['relationships']
        self.assertEqual(result['entries'][0]['day'],'2027-01-15')
        self.assertEqual(result['activities'][0]['day'],'2026-01-10')
        self.assertEqual(self.request('/api/relationships/entries/entry','PATCH',{**payload,'completedDay':'2099-01-01'})[0],400)
        self.request('/api/relationships/activity/'+result['activities'][0]['id'],'DELETE',{})
        self.stop_server();self.start_server()
        result=self.request()[1]['relationships']
        self.assertEqual(result['activities'],[]);self.assertFalse(result['entries'][0]['done'])
        payload.pop('completedDay')
        result=self.request('/api/relationships/entries/entry','PATCH',payload)[1]['relationships']
        self.assertEqual(result['activities'][0]['day'],today())
        self.request('/api/relationships/entries/entry','PATCH',{**payload,'done':False})
        self.assertEqual(self.request()[1]['relationships']['activities'],[])

    def test_old_completion_marks_migrate_without_future_activity_or_duplicates(self):
        self.request('/api/relationships/entries','POST',self.entry('gift'))
        future=self.entry('care');future.update(id='future',day='2099-01-01')
        self.request('/api/relationships/entries','POST',future)
        self.stop_server()
        with self.server.store.connect() as db:
            db.execute('DELETE FROM relationship_activity')
            db.execute('ALTER TABLE relationship_entries DROP COLUMN completed_day')
            db.execute("UPDATE relationship_entries SET done=1,day='2026-01-10' WHERE id='entry'")
            db.execute("UPDATE relationship_entries SET done=1 WHERE id='future'")
        self.start_server()
        result=self.request()[1]['relationships']
        self.assertEqual(len(result['activities']),2)
        self.assertEqual(next(a for a in result['activities'] if a['kind']=='gift')['day'],'2026-01-10')
        self.assertNotEqual(next(a for a in result['activities'] if a['kind']=='care')['day'],'2099-01-01')
        self.stop_server();self.start_server()
        self.assertEqual(len(self.request()[1]['relationships']['activities']),2)


if __name__=='__main__':unittest.main()
