from test_server import ServerFixture


class DayTaskTests(ServerFixture):
    def task(self,**changes):
        return {**dict(id='task',title='Prepare',note='Bring a notebook',day='2027-01-15',time='10:30',priority='high',done=False),**changes}

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
