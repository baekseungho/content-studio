import json,os,threading,time,unittest,urllib.error,urllib.request
from unittest.mock import patch
import app

class LogicHttpTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.server=app.ThreadingHTTPServer(('127.0.0.1',0),app.Handler);cls.host='127.0.0.1:'+str(cls.server.server_address[1]);app.HOSTS.add(cls.host);cls.base='http://'+cls.host
  cls.thread=threading.Thread(target=cls.server.serve_forever,daemon=True);cls.thread.start()
 @classmethod
 def tearDownClass(cls):cls.server.shutdown();cls.server.server_close();cls.thread.join();app.HOSTS.discard(cls.host)
 def post(self,path,body):
  req=urllib.request.Request(self.base+path,data=json.dumps(body).encode(),headers={'Content-Type':'application/json','X-Studio-Token':app.TOKEN})
  try:
   with urllib.request.urlopen(req,timeout=5) as response:return response.status,json.load(response)
  except urllib.error.HTTPError as error:
   with error:return error.code,json.load(error)
 def wait(self,jid):
  for _ in range(300):
   with app.JOB_LOCK:done=app.JOBS[jid]['state']!='running'
   if done:return
   time.sleep(.005)
  self.fail('worker not complete')
 def test_duplicate_generations_are_refused_over_http_before_second_model_call(self):
  release=threading.Event();started=threading.Event()
  def generate(*args):started.set();release.wait(3);return {'title':'fixture','blog':'fixture'}
  with patch.dict(app.JOBS,{},clear=True),patch.object(app,'generate',side_effect=generate) as model:
   status,first=self.post('/api/generate',{'platforms':['naver'],'prompt':'test'});self.assertEqual(status,200);self.assertTrue(started.wait(1))
   try:
    status,second=self.post('/api/generate',{'platforms':['naver'],'prompt':'test'})
    self.assertEqual(status,409);self.assertEqual(second['code'],'job_in_progress');self.assertEqual(model.call_count,1)
    status,repair=self.post('/api/blog/expand',{'platforms':['naver']})
    self.assertEqual(status,409);self.assertEqual(repair['code'],'job_in_progress')
   finally:release.set();self.wait(first['job'])
 def test_photo_disconnect_waits_for_active_publication(self):
  release=threading.Event()
  with patch.dict(app.JOBS,{},clear=True),patch.object(app.PHOTO_TUNNEL,'close') as close:
   jid=app.start_job(lambda:release.wait(3),kind='publishing')['job']
   try:self.assertEqual(self.post('/api/media/disconnect',{})[0],409);close.assert_not_called()
   finally:release.set();self.wait(jid)
   self.assertEqual(self.post('/api/media/disconnect',{})[0],200);close.assert_called_once()
 def test_invalid_naver_identity_does_not_allocate_handoff_ticket(self):
  with patch.object(app,'get_draft',return_value={'id':'a'*32}),patch.dict(os.environ,{'NAVER_BLOG_ID':'invalid/path'}),patch.object(app.EXTENSION,'create') as create:
   status,result=self.post('/api/naver/handoff',{'id':'a'*32})
   self.assertEqual(status,400);create.assert_not_called()

 def test_new_job_cannot_slip_into_the_middle_of_photo_disconnect(self):
  entered=threading.Event();release=threading.Event();started=threading.Event();reply=[];jobs=[]
  def close():entered.set();release.wait(2)
  def submit():jobs.append(app.start_job(lambda:started.set(),kind='publishing')['job'])
  with patch.dict(app.JOBS,{},clear=True),patch.object(app.PHOTO_TUNNEL,'close',side_effect=close):
   disconnect=threading.Thread(target=lambda:reply.append(self.post('/api/media/disconnect',{})));disconnect.start();self.assertTrue(entered.wait(1))
   publish=threading.Thread(target=submit);publish.start()
   try:self.assertFalse(started.wait(.05))
   finally:release.set();disconnect.join(3);publish.join(3)
   self.assertFalse(disconnect.is_alive());self.assertFalse(publish.is_alive());self.assertEqual(reply[0][0],200);self.assertEqual(len(jobs),1);self.wait(jobs[0])

 def test_tistory_unlock_requires_confirmation_and_keeps_cooldown(self):
  import tempfile
  from pathlib import Path
  from extension_bridge import ExtensionBridge
  from naver_guard import NaverGuard
  with tempfile.TemporaryDirectory() as folder:
   root=Path(folder);guard=NaverGuard(root/'guard.json');guard.reserve('fixture');guard.block('추가 인증');bridge=ExtensionBridge(root,guard,channel='tistory')
   with patch.object(app,'TISTORY_EXTENSION',bridge):
    self.assertEqual(self.post('/api/tistory/unblock',{})[0],400);self.assertTrue(guard.status()['blocked'])
    status,result=self.post('/api/tistory/unblock',{'confirm':True});self.assertEqual(status,200);self.assertFalse(result['blocked']);self.assertGreater(result['cooldown_seconds'],0)
 def test_inspection_is_readonly_and_uses_the_extension_origin_rules(self):
  import tempfile
  from pathlib import Path
  from extension_bridge import ExtensionBridge
  from naver_guard import NaverGuard
  with tempfile.TemporaryDirectory() as folder:
   root=Path(folder);bridge=ExtensionBridge(root,NaverGuard(root/'guard.json'));writer='https://blog.naver.com/fixture?Redirect=Write&';code=bridge.create({'id':'a'*32,'title':'private title','blog':'private body','images':[]},writer_url=writer)['code']
   with patch.object(app,'EXTENSION',bridge):
    self.assertEqual(self.post('/api/extension/inspect',{'code':code})[0],403)
    request=urllib.request.Request(self.base+'/api/extension/inspect',data=json.dumps({'code':code}).encode(),headers={'Content-Type':'application/json','X-Dajeong-Extension':'1','Origin':'chrome-extension://'+'a'*32})
    with urllib.request.urlopen(request) as response:result=json.load(response)
   self.assertEqual(result['writer_url'],writer);self.assertNotIn('body',result);self.assertNotIn('title',result);self.assertIn(code,bridge.tickets);self.assertEqual(bridge.guard.status()['attempts_24h'],0)
