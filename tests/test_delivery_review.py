"""The reviewed saved revision is the one delivered, even when a worker starts later."""
import json,os,unittest
from pathlib import Path
from unittest.mock import patch
from PIL import Image
import app,delivery_review
import test_writing_api as api_fixture
from threads_publishing import SCHEMA

class DeliveryReviewTests(unittest.TestCase):
 call=api_fixture.WritingAPITests.call
 def setUp(self):
  api_fixture.WritingAPITests.setUp(self);self.root=Path(self.temp.name);self.media=self.root/'media';self.media.mkdir()
  self.patches=[patch.object(app,'DATA',self.root),patch.object(app,'MEDIA',self.media),patch.dict(os.environ,{'NAVER_BLOG_ID':'sample-blog'})]
  for item in self.patches:item.start()
  with app.db() as conn:conn.executescript('CREATE TABLE drafts(id TEXT PRIMARY KEY,title TEXT,data TEXT,updated REAL);CREATE TABLE attempts(id TEXT PRIMARY KEY,draft_id TEXT,state TEXT,result TEXT,created REAL);'+SCHEMA)
  self.mid='a'*32;Image.new('RGB',(600,400),'#aabbcc').save(self.media/(self.mid+'.jpg'))
  self.draft=app.save_draft({'title':'네이버 이야기','blog':'창가에서 라떼를 마셨어요.','tistory_title':'Tistory story','tistory':'A little coffee break.','threads':'A little coffee break.','instagram':'A little coffee break.','language':'en','platform_languages':{'naver':'ko','tistory':'en','instagram':'en','threads':'en'},'images':[self.mid],'selective_generation':True,'selected_platforms':['naver','instagram','threads','tistory']})
 def tearDown(self):
  for item in reversed(self.patches):item.stop()
  api_fixture.WritingAPITests.tearDown(self)
 def request(self,p='naver'):return {'id':self.draft['id'],'updated':self.draft['updated'],'platform':p,'blog_url':'https://sample.tistory.com','confirm':True,'with_images':False}
 def test_preview_requires_auth_and_revision(self):
  self.assertEqual(self.call('/api/delivery/preview',self.request(),False)[0],403)
  body=self.request();del body['updated'];self.assertEqual(self.call('/api/delivery/preview',body)[0],400);self.assertFalse(app.JOBS)
 def test_preview_is_local_readonly_and_has_exact_photo_order_and_format(self):
  with patch.object(app,'remote',side_effect=AssertionError('No external calls')),patch.object(app.PHOTO_TUNNEL,'allow',side_effect=AssertionError('No public media')):
   status,result=self.call('/api/delivery/preview',self.request())
  self.assertEqual(status,200);self.assertTrue(result['ready']);self.assertEqual(result['effect'],'editor');self.assertEqual(result['title'],'네이버 이야기');self.assertEqual(result['language'],'ko');self.assertEqual(result['target_url'],'https://blog.naver.com/sample-blog');self.assertEqual(result['format']['align'],'center');self.assertEqual([p['id'] for p in result['photos']],[self.mid]);self.assertEqual(result['photos'][0]['width'],600);self.assertIn('[[photo:1]]',result['text']);self.assertFalse(app.JOBS);self.assertEqual(app.get_draft(self.draft['id'])['updated'],self.draft['updated'])
 def test_tistory_has_its_own_body_language_and_address(self):
  _,result=self.call('/api/delivery/preview',self.request('tistory'));self.assertEqual(result['title'],'Tistory story');self.assertIn('A little coffee',result['text']);self.assertEqual(result['language'],'en');self.assertEqual(result['target_url'],'https://sample.tistory.com/manage/newpost/')
 def test_threads_text_only_excludes_selected_photos(self):
  _,result=self.call('/api/delivery/preview',self.request('threads'));self.assertEqual(result['photos'],[]);self.assertEqual(result['effect'],'public');self.assertEqual(result['text'],self.draft['threads'])
 def test_channel_specific_photos_are_inspected(self):
  draft=app.save_draft({**self.draft,'channel_media':{'instagram':{'version':1,'images':[],'frame':'square','adjustments':{}}}})
  _,result=self.call('/api/delivery/preview',{**self.request('instagram'),'updated':draft['updated']});self.assertFalse(result['ready']);self.assertEqual(result['photos'],[])
 def test_missing_and_corrupt_photos_are_blocked_with_location(self):
  for raw in (None,b'not an image'):
   path=self.media/(self.mid+'.jpg')
   if raw is None:path.unlink()
   else:path.write_bytes(raw)
   _,result=self.call('/api/delivery/preview',self.request());self.assertFalse(result['ready']);issue=next(c for c in result['checks'] if c.get('photo_number')==1);self.assertEqual(issue['field'],'photos');self.assertFalse(result['photos'][0]['available'])
 def test_all_delivery_routes_reject_stale_revision_without_creating_work(self):
  with patch.object(app,'remote',side_effect=AssertionError('No external calls')):
   for route in ('/api/delivery/preview','/api/naver/handoff','/api/tistory/handoff','/api/publish/instagram','/api/publish/threads'):
    with self.subTest(route=route):
     status,result=self.call(route,{**self.request(),'updated':self.draft['updated']-1});self.assertEqual(status,409);self.assertEqual(result['code'],'delivery_conflict');self.assertFalse(app.JOBS)
 def test_bad_revision_and_channel_are_rejected(self):
  for revision in (True,'1',float('inf')):self.assertEqual(self.call('/api/delivery/preview',{**self.request(),'updated':revision})[0],400)
  self.assertEqual(self.call('/api/delivery/preview',{**self.request(),'platform':'unknown'})[0],400)
 def test_snapshot_is_deep_and_preserves_content_after_later_save(self):
  frozen=delivery_review.snapshot(self.draft,self.request(),True);changed=app.save_draft({**self.draft,'threads':'A newer saved thought.'});self.assertNotEqual(changed['threads'],frozen['threads']);self.draft['images'].clear();self.assertEqual(frozen['images'],[self.mid])
 def test_queued_instagram_job_does_not_read_later_revision(self):
  pending=[]
  def queue(fn,**kwargs):pending.append(fn);return {'job':'b'*32}
  with patch.object(app,'start_job',side_effect=queue),patch.object(app,'publish_instagram') as publish:
   self.assertEqual(self.call('/api/publish/instagram',self.request('instagram'))[0],200)
   app.save_draft({**self.draft,'instagram':'A different later caption.'});pending[0]();self.assertEqual(publish.call_args.kwargs['snapshot']['instagram'],self.draft['instagram'])
 def test_queued_threads_job_does_not_read_later_revision(self):
  pending=[]
  def queue(fn,**kwargs):pending.append(fn);return {'job':'b'*32}
  with patch.object(app,'start_job',side_effect=queue),patch.object(app,'threads_service') as service:
   self.assertEqual(self.call('/api/publish/threads',self.request('threads'))[0],200)
   app.save_draft({**self.draft,'threads':'A different later thought.'});pending[0](lambda message:None);self.assertEqual(service.return_value.publish.call_args.kwargs['snapshot']['threads'],self.draft['threads']);self.assertFalse(service.return_value.publish.call_args.args[2])

 def test_instagram_publisher_uses_frozen_content_without_reading_changed_draft(self):
  frozen=delivery_review.snapshot(self.draft,self.request(),True);app.save_draft({**self.draft,'instagram':'Later content that was never confirmed.'});calls=[]
  def graph(path,payload):calls.append((path,payload));return {'id':'published' if path.endswith('/media_publish') else 'container'}
  with patch.object(app,'get_draft',side_effect=AssertionError('Must not reload')),patch.object(app,'instagram_configuration',return_value={'ready':True}),patch.object(app,'media_base_url',return_value='https://media.example.test'),patch.object(app,'graph',side_effect=graph),patch.object(app,'wait_container'),patch.object(app.PHOTO_TUNNEL,'active',return_value=False):
   result=app.publish_instagram(self.draft['id'],snapshot=frozen)
  self.assertEqual(result['state'],'published');self.assertEqual(calls[0][1]['caption'],frozen['instagram'])
 def test_threads_publisher_uses_frozen_content_without_reading_changed_draft(self):
  frozen=delivery_review.snapshot(self.draft,self.request(),True);app.save_draft({**self.draft,'threads':'Later content that was never confirmed.'});calls=[]
  def graph(path,payload):calls.append((path,payload));return {'id':'published' if path.endswith('/threads_publish') else 'container'}
  with patch.object(app,'get_draft',side_effect=AssertionError('Must not reload')),patch.dict(os.environ,{'THREADS_USER_ID':'777'}):
   service=app.threads_service()
   with patch.object(service,'configuration',return_value={'ready':True,'media_ready':True}),patch.object(service,'check',return_value={'account_matches':True}),patch.object(service,'graph',side_effect=graph),patch.object(service,'wait_all'):
    result=service.publish(self.draft['id'],with_images=False,snapshot=frozen)
  self.assertEqual(result['state'],'published');self.assertEqual(calls[0][1]['text'],frozen['threads']);self.assertEqual(calls[0][1]['media_type'],'TEXT')
