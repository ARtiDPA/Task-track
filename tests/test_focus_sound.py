import unittest
from pathlib import Path
from playwright.sync_api import sync_playwright


class FocusSoundTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.playwright=sync_playwright().start();cls.browser=cls.playwright.chromium.launch(channel='msedge',headless=True)

    @classmethod
    def tearDownClass(cls):cls.browser.close();cls.playwright.stop()

    def setUp(self):
        self.page=self.browser.new_page()
        self.page.evaluate('''()=>{
          window.audioTime=0;window.tones=[];window.completions=[];
          window.AudioContext=class {
            constructor(){this.state='suspended';this.destination={};}
            get currentTime(){return window.audioTime;}
            async resume(){this.state='running';}
            createGain(){return {gain:{setValueAtTime(){},linearRampToValueAtTime(){},exponentialRampToValueAtTime(){}},connect(){},disconnect(){}};}
            createOscillator(){const node={frequency:{setValueAtTime(){}},connect(){},disconnect(){},start(at){this.at=at;},stop(at){if(at===undefined)this.cancelled=true;}};window.tones.push(node);return node;}
          };
          window.addEventListener('ritmo:focus-sound',e=>window.completions.push(e.detail.sessionId));
        }''')
        self.page.add_script_tag(path=str(Path(__file__).resolve().parents[1]/'focus-sound.js'))

    def tearDown(self):self.page.close()

    def test_alarm_is_scheduled_once_and_not_replayed_after_background_audio(self):
        self.page.evaluate("async()=>{await RitmoFocusSound.unlock();RitmoFocusSound.sync({id:'one',status:'running',remainingMs:60000});RitmoFocusSound.sync({id:'one',status:'running',remainingMs:60000});}")
        self.assertEqual(self.page.evaluate('tones.length'),3)
        self.assertEqual(self.page.evaluate('tones[0].at'),60)
        self.page.evaluate("()=>{audioTime=62;tones[0].onended();tones[2].onended();RitmoFocusSound.complete('one');RitmoFocusSound.complete('one');RitmoFocusSound.sync(null);}")
        self.assertEqual(self.page.evaluate('tones.length'),3)
        self.assertEqual(self.page.evaluate('completions'),['one'])

    def test_pause_cancels_audio_and_resume_reschedules_remaining_time(self):
        self.page.evaluate("async()=>{await RitmoFocusSound.unlock();RitmoFocusSound.sync({id:'one',status:'running',remainingMs:60000});RitmoFocusSound.sync({id:'one',status:'paused',remainingMs:45000});}")
        self.assertTrue(self.page.evaluate('tones.every(n=>n.cancelled)'))
        self.page.evaluate("()=>{audioTime=20;RitmoFocusSound.sync({id:'one',status:'running',remainingMs:45000});}")
        self.assertEqual(self.page.evaluate('tones[3].at'),65)
        self.page.evaluate('RitmoFocusSound.sync(null)')
        self.assertTrue(self.page.evaluate('tones.every(n=>n.cancelled)'))
        self.assertEqual(self.page.evaluate('completions'),[])

    def test_completion_waits_for_user_gesture_when_audio_was_not_unlocked(self):
        self.page.evaluate("()=>{RitmoFocusSound.complete('one');RitmoFocusSound.complete('one');}")
        self.assertEqual(self.page.evaluate('tones.length'),0)
        self.page.evaluate('RitmoFocusSound.unlock(true)')
        self.assertEqual(self.page.evaluate('tones.length'),3)
        self.page.evaluate("RitmoFocusSound.complete('one')")
        self.assertEqual(self.page.evaluate('tones.length'),3)
