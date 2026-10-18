from test_server import ServerFixture


class DayTaskTests(ServerFixture):
    def task(self,**changes):
        return {**dict(id='task',title='Prepare',note='Bring a notebook',day='2027-01-15',time='10:30',priority='high',done=False,checklist=[]),**changes}

    def test_tasks_reschedule_complete_and_survive_restart(self):
        payload=self.task()
        self.assertEqual(self.request('/api/tasks','POST',payload)[0],200)
        self.request('/api/tasks','POST',payload)
        self.assertEqual(len(self.request()[1]['tasks']),1)
        payload.update(day='2027-01-16',done=True)
        self.assertEqual(self.request('/api/tasks/task','PATCH',payload)[0],200)
        self.stop_server();self.start_server()
        self.assertEqual(self.request()[1]['tasks'][0],payload)
        payload.update(day='',time='',done=False)
        self.request('/api/tasks/task','PATCH',payload)
        result=self.request()[1]
        self.assertEqual(result['tasks'][0]['day'],'')
        self.assertEqual(result['organizer']['events'],[])
        self.assertEqual(result['finance']['transactions'],[])
        self.assertEqual(self.request('/api/tasks/task','DELETE',{})[0],200)
        self.assertEqual(self.request()[1]['tasks'],[])

    def test_task_validation_and_profile_isolation(self):
        for key,value in [('day','2027-02-30'),('time','25:00'),('priority','urgent'),('done',1),('title',''),('note','x'*3001),('day','')]:
            self.assertEqual(self.request('/api/tasks','POST',self.task(**{key:value}))[0],400,key)
        self.request('/api/tasks','POST',self.task())
        self.request('/api/auth/register','POST',dict(email='other@example.com',name='Other',password='other-password'))
        self.assertEqual(self.request()[1]['tasks'],[])
        self.assertEqual(self.request('/api/tasks/task','PATCH',self.task())[0],404)
        self.assertEqual(self.request('/api/tasks/task','DELETE',{})[0],404)

    def test_checklists_sync_parent_status_validate_and_survive_restart(self):
        payload=self.task(checklist=[dict(id='a',title='First',done=False),dict(id='b',title='Second',done=False)])
        self.request('/api/tasks','POST',payload)
        result=self.request('/api/tasks/task/items/a','PATCH',dict(done=True))[1]['tasks'][0]
        self.assertTrue(result['checklist'][0]['done']);self.assertFalse(result['done'])
        result=self.request('/api/tasks/task','PATCH',{**result,'done':True})[1]['tasks'][0]
        self.assertTrue(all(i['done'] for i in result['checklist']))
        result=self.request('/api/tasks/task/items/b','PATCH',dict(done=False))[1]['tasks'][0]
        self.assertFalse(result['done']);self.assertFalse(result['checklist'][1]['done'])
        self.stop_server();self.start_server()
        self.assertEqual(self.request()[1]['tasks'][0]['checklist'],result['checklist'])
        self.assertEqual(self.request('/api/tasks/task','PATCH',{**result,'checklist':[dict(id='x',title='',done=False)]})[0],400)
        self.request('/api/auth/register','POST',dict(email='other@example.com',name='Other',password='other-password'))
        self.assertEqual(self.request('/api/tasks/task/items/a','PATCH',dict(done=True))[0],404)
