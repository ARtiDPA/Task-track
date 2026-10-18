from datetime import datetime,timezone,timedelta
from unittest.mock import patch
from test_server import ServerFixture


class FocusTests(ServerFixture):
    def setUp(self):
        super().setUp();self.clock=1780000000000
        self.mock=patch('focus.now_ms',side_effect=lambda:self.clock);self.mock.start()

    def tearDown(self):
        self.mock.stop();super().tearDown()

    def start(self,id='focus',minutes=1):return self.request('/api/focus/sessions','POST',dict(id=id,title='Study',minutes=minutes))
    def action(self,name,id='focus'):return self.request('/api/focus/sessions/'+id+'/'+name,'POST',{})

    def test_pauses_do_not_count_and_reload_keeps_active_session(self):
        self.assertEqual(self.start()[0],200);self.start()
        self.clock+=20000;result=self.action('pause')[1]['focus']
        self.assertEqual(result['active']['elapsedMs'],20000);self.assertEqual(result['totalMs'],20000)
        self.clock+=120000;self.assertEqual(self.request()[1]['focus']['totalMs'],20000)
        self.stop_server();self.start_server()
        self.assertEqual(self.request()[1]['focus']['active']['status'],'paused')
        self.action('resume');self.clock+=10000;result=self.action('finish')[1]['focus']
        self.assertIsNone(result['active']);self.assertEqual(result['totalMs'],30000)
        self.assertEqual(result['history'][0]['elapsedMs'],30000)
        self.action('finish');self.assertEqual(self.request()[1]['focus']['sessionCount'],1)

    def test_timer_caps_at_target_and_reconciles_once_without_browser(self):
        self.start();self.clock+=3600000
        result=self.request()[1]['focus']
        self.assertIsNone(result['active']);self.assertEqual(result['totalMs'],60000)
        self.assertEqual(result['history'][0]['elapsedMs'],60000)
        self.clock+=60000;self.assertEqual(self.request()[1]['focus']['totalMs'],60000)
        self.start('second');self.assertEqual(self.start('third')[0],400)
        self.action('cancel','second');self.assertIsNone(self.request()[1]['focus']['active'])

    def test_distraction_pause_undo_history_and_day_boundary(self):
        tz=timezone(timedelta(hours=3))
        self.clock=int(datetime(2026,10,18,23,59,40,tzinfo=tz).timestamp()*1000)
        self.start();self.clock+=40000
        result=self.action('distract')[1]['focus']
        self.assertEqual(result['distractions'],1)
        self.action('distract');self.assertEqual(self.request()[1]['focus']['distractions'],1)
        self.assertEqual(result['daily'],[dict(day='2026-10-18',milliseconds=20000),dict(day='2026-10-19',milliseconds=20000)])
        self.action('finish');self.request('/api/focus/sessions/focus','DELETE',{})
        result=self.request()[1]['focus'];self.assertEqual(result['totalMs'],0);self.assertEqual(result['daily'],[])

    def test_validation_and_profile_isolation(self):
        self.assertEqual(self.start(minutes=True)[0],400);self.assertEqual(self.start(minutes=181)[0],400)
        self.start();self.assertEqual(self.request('/api/focus/sessions/focus','DELETE',{})[0],400)
        self.assertEqual(self.request('/api/focus/settings','PUT',dict(goalMinutes=0,autoPause=True))[0],400)
        self.request('/api/focus/settings','PUT',dict(goalMinutes=60,autoPause=False))
        self.request('/api/auth/register','POST',dict(email='second@example.com',name='Other',password='other-password'))
        result=self.request()[1]['focus'];self.assertIsNone(result['active']);self.assertEqual(result['totalMs'],0)
        self.assertTrue(result['settings']['autoPause']);self.assertEqual(self.action('finish')[0],404)
