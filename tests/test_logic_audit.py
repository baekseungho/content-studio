import concurrent.futures,json,os,sqlite3,tempfile,threading,time,unittest
from pathlib import Path
from unittest.mock import patch
from PIL import Image
import app
from extension_bridge import ExtensionBridge,HandoffError
from naver_guard import NaverGuard
from publish_media import prepare_photo
from writing_quality import publication_errors

class SaveConflictTests(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name);self.data=patch.object(app,'DATA',self.root);self.data.start()
  with app.db() as db:db.execute('CREATE TABLE drafts(id TEXT PRIMARY KEY,title TEXT,data TEXT,updated REAL)')
 def tearDown(self):self.data.stop();self.temp.cleanup()
 def create(self):return app.save_draft({'title':'제목','blog':'원문','threads':'스레드 원고','editing_platform':'threads'})
 def test_last_editing_platform_survives_save_and_reload(self):
  saved=self.create();self.assertEqual(saved['editing_platform'],'threads');self.assertEqual(app.get_draft(saved['id'])['editing_platform'],'threads')
 def test_stale_window_cannot_overwrite_newer_text_or_drop_revision(self):
  first=self.create();second=app.get_draft(first['id']);newer=app.save_draft({**first,'blog':'더 최근에 저장한 글'})
  with self.assertRaises(app.Problem) as error:app.save_draft({**second,'blog':'오래된 화면의 수정'})
  self.assertEqual(error.exception.code,'draft_conflict');self.assertEqual(error.exception.status,409)
  self.assertEqual(app.get_draft(first['id'])['blog'],newer['blog'])
  for version in (None,True,float('nan')):
   with self.assertRaises(app.Problem):app.save_draft({**second,'updated':version})
 def test_simultaneous_saves_have_exactly_one_winner(self):
  saved=self.create();barrier=threading.Barrier(2)
  def update(label):
   barrier.wait()
   try:return app.save_draft({**saved,'blog':label})
   except app.Problem as error:return error
  with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:results=list(executor.map(update,['첫 번째 창','두 번째 창']))
  self.assertEqual(sum(isinstance(row,dict) for row in results),1)
  self.assertEqual(sum(isinstance(row,app.Problem) and row.code=='draft_conflict' for row in results),1)
 def test_new_id_preserves_both_revisions(self):
  first=self.create();newer=app.save_draft({**first,'blog':'최신 원고'})
  copy=app.save_draft({**first,'id':'c'*32,'blog':'다른 창의 원고'})
  self.assertNotEqual(first['id'],copy['id']);self.assertEqual(app.get_draft(first['id'])['blog'],newer['blog'])

class JobCoordinationTests(unittest.TestCase):
 def wait(self,jid):
  for _ in range(200):
   with app.JOB_LOCK:done=app.JOBS[jid]['state']!='running'
   if done:return
   time.sleep(.005)
  self.fail('Job did not finish')
 def test_second_generation_or_repair_does_not_start_while_first_runs(self):
  release=threading.Event();calls=[]
  def work():calls.append('started');release.wait(2);return {'ok':True}
  with patch.dict(app.JOBS,{},clear=True):
   first=app.start_job(work,kind='writing')['job']
   try:
    with self.assertRaises(app.Problem) as error:app.start_job(lambda:calls.append('duplicate'),kind='writing')
    self.assertEqual(error.exception.code,'job_in_progress');self.assertTrue(app.jobs_running('writing'))
   finally:release.set();self.wait(first)
   self.assertEqual(calls,['started']);self.assertFalse(app.jobs_running('writing'))
 def test_completed_history_is_bounded_and_running_jobs_are_kept(self):
  with patch.dict(app.JOBS,{'running':{'state':'running','_created':0},**{str(i):{'state':'done','_finished':i} for i in range(140)}},clear=True):
   with app.JOB_LOCK:app._prune_jobs(150)
   self.assertIn('running',app.JOBS);self.assertLess(len(app.JOBS),app.MAX_STORED_JOBS)
   with app.JOB_LOCK:app._prune_jobs(10000)
   self.assertEqual(set(app.JOBS),{'running'})
 def test_worker_start_failure_does_not_leave_a_permanent_running_job(self):
  with patch.dict(app.JOBS,{},clear=True),patch('app.threading.Thread.start',side_effect=RuntimeError('test')):
   with self.assertRaises(app.Problem):app.start_job(lambda:None,kind='writing')
   self.assertEqual(app.JOBS,{})
 def test_many_running_jobs_are_rejected_without_new_worker(self):
  with patch.dict(app.JOBS,{str(i):{'state':'running'} for i in range(app.MAX_RUNNING_JOBS)},clear=True),patch('app.threading.Thread.start') as start:
   with self.assertRaises(app.Problem):app.start_job(lambda:None)
   start.assert_not_called()

class PublicationGateTests(unittest.TestCase):
 def test_blog_review_ignores_unfinished_other_platforms(self):
  self.assertEqual(publication_errors({'title':'제목','blog':'본문','instagram':'가'*2201,'threads':'가'*501},'naver'),[])
 def test_handoff_blocks_length_and_language_errors_before_consuming_guard(self):
  with tempfile.TemporaryDirectory() as folder:
   root=Path(folder);guard=NaverGuard(root/'guard.json');bridge=ExtensionBridge(root,guard)
   for draft in ({'title':'제목','blog':'가'*5001},{'title':'','blog':'본문'},{'title':'Title','blog':'Mixed 한국어','platform_languages':{'naver':'en'}}):
    with self.assertRaises(HandoffError):bridge.create({'id':'a'*32,'images':[],**draft})
   self.assertEqual(bridge.tickets,{});self.assertEqual(guard.status()['attempts_24h'],0)
 def test_threads_mixed_language_uses_its_own_language_before_any_external_call(self):
  draft={'threads':'한글이 남은 영어 원고','language':'ko','platform_languages':{'threads':'en'},'images':[]}
  service=app.threads_service()
  with patch.object(service,'get_draft',return_value=draft),patch.object(service,'configuration',return_value={'ready':True}),patch.object(service,'remote') as remote:
   with self.assertRaisesRegex(app.Problem,'한국어'):service.publish('a'*32)
   remote.assert_not_called()
 def test_instagram_invalid_english_is_rejected_before_any_external_call(self):
  draft={'instagram':'Mixed 한국어','language':'ko','platform_languages':{'instagram':'en'},'images':['a'*32]}
  with patch.object(app,'get_draft',return_value=draft),patch.object(app,'instagram_configuration',return_value={'ready':True}),patch.object(app,'media_base_url',return_value='https://photos.example.com'),patch.object(app,'graph') as graph:
   with self.assertRaisesRegex(app.Problem,'한국어'):app.publish_instagram('b'*32)
   graph.assert_not_called()

class AtomicMediaTests(unittest.TestCase):
 def test_two_channels_never_leave_a_partial_target_or_temp_files(self):
  with tempfile.TemporaryDirectory() as folder:
   root=Path(folder);mid='a'*32;Image.new('RGB',(40,30),'red').save(root/(mid+'.jpg'))
   with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:paths=list(executor.map(lambda _:prepare_photo(root,mid),range(8)))
   self.assertTrue(all(path==paths[0] for path in paths))
   with Image.open(paths[0]) as image:image.load();self.assertEqual(image.size,(1080,1350))
   self.assertEqual(list(root.glob('*.tmp')),[])
 def test_failed_conversion_preserves_the_previous_complete_photo(self):
  with tempfile.TemporaryDirectory() as folder:
   root=Path(folder);mid='a'*32;Image.new('RGB',(40,30),'red').save(root/(mid+'.jpg'));target=prepare_photo(root,mid);original=target.read_bytes()
   with patch('publish_media.Image.Image.save',side_effect=OSError('disk full')):
    with self.assertRaises(OSError):prepare_photo(root,mid)
   self.assertEqual(target.read_bytes(),original);self.assertEqual(list(root.glob('*.tmp')),[])


class CorruptGuardTests(unittest.TestCase):
 def test_corrupt_state_shape_blocks_input_instead_of_breaking_the_whole_app(self):
  with tempfile.TemporaryDirectory() as folder:
   guard=NaverGuard(Path(folder)/'guard.json')
   for state in ([],None,{'attempts':['bad']},{'attempts':[float('nan')]},{'completed':123},{'blocked':'yes'},{'reason':None}):
    guard.path.write_text(json.dumps(state),encoding='utf-8')
    self.assertTrue(guard.status()['blocked'])
    with self.assertRaises(ValueError):guard.reserve('a')
