import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from PIL import Image
import app
from threads_publishing import SCHEMA

class ThreadsPublishingTests(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name);self.media=self.root/'media';self.media.mkdir()
  self.patches=[patch.object(app,'DATA',self.root),patch.object(app,'MEDIA',self.media),patch.dict(os.environ,{'THREADS_USER_ID':'777','THREADS_ACCESS_TOKEN':'threads-test-only','THREADS_API_VERSION':'v1.0','INSTAGRAM_ACCESS_TOKEN':'instagram-separate'}),patch.object(app,'media_base_url',return_value='https://photos.example.com')]
  for item in self.patches:item.start()
  with app.db() as db:
   db.executescript("CREATE TABLE drafts(id TEXT PRIMARY KEY,title TEXT,data TEXT,updated REAL);CREATE TABLE attempts(id TEXT PRIMARY KEY,draft_id TEXT,state TEXT,result TEXT,created REAL);"+SCHEMA)
  self.calls=[]
 def tearDown(self):
  for item in reversed(self.patches):item.stop()
  self.temp.cleanup()
 def draft(self,count=0):
  images=[]
  for i in range(count):
   mid=str(i+1)*32;Image.new('RGB',(10,8),'red').save(self.media/(mid+'.jpg'));images.append(mid)
  return app.save_draft({'title':'공통 초안','blog':'본문','threads':'오늘의 작은 이야기 🤍','images':images})
 def fake(self,url,payload=None,token=None,timeout=60,form=False):
  self.calls.append((url,payload,token,form))
  if '/me?' in url:return {'id':'777','username':'sample'}
  if '?fields=status' in url:return {'status':'FINISHED'}
  if url.endswith('/threads_publish'):return {'id':'published-threads'}
  return {'id':'container-'+str(len(self.calls))}
 def test_text_publish_without_media_url_and_separate_token(self):
  draft=self.draft()
  with patch.object(app,'media_base_url',return_value=''),patch.object(app,'remote',side_effect=self.fake):
   result=app.threads_service().publish(draft['id'])
  self.assertEqual(result['media_id'],'published-threads')
  creates=[body for url,body,token,form in self.calls if url.endswith('/threads')]
  self.assertEqual(creates,[{'media_type':'TEXT','text':draft['threads']}])
  self.assertTrue(all(token=='threads-test-only' and form for _,_,token,form in self.calls))
  self.assertTrue(all(url.startswith('https://graph.threads.com/v1.0/') for url,_,_,_ in self.calls))
 def test_single_photo_and_carousel(self):
  for count in (1,2):
   draft=self.draft(count);self.calls=[]
   with patch.object(app,'remote',side_effect=self.fake):app.threads_service().publish(draft['id'])
   image_calls=[body for url,body,_,_ in self.calls if body and body.get('media_type')=='IMAGE']
   self.assertEqual(len(image_calls),count)
   self.assertTrue(all(body['image_url'].endswith('-ig.jpg') for body in image_calls))
   if count==1:self.assertEqual(image_calls[0]['text'],draft['threads'])
   else:
    self.assertTrue(all(body['is_carousel_item'] is True and 'text' not in body for body in image_calls))
    parent=[body for _,body,_,_ in self.calls if body and body.get('media_type')=='CAROUSEL'][0]
    self.assertEqual(len(parent['children'].split(',')),2);self.assertEqual(parent['text'],draft['threads'])
 def test_photo_can_be_excluded_and_missing_media_is_blocked(self):
  draft=self.draft(1)
  with patch.object(app,'media_base_url',return_value=''),patch.object(app,'remote',side_effect=self.fake):
   with self.assertRaises(app.Problem):app.threads_service().publish(draft['id'])
   self.assertFalse(self.calls)
   app.threads_service().publish(draft['id'],with_images=False)
  self.assertTrue(any(body and body.get('media_type')=='TEXT' for _,body,_,_ in self.calls))
 def test_mismatched_account_prevents_writes(self):
  draft=self.draft()
  with patch.object(app,'remote',return_value={'id':'888'}) as remote:
   with self.assertRaises(app.Problem):app.threads_service().publish(draft['id'])
  self.assertEqual(remote.call_count,1)
  self.assertIsNone(remote.call_args.args[1])
 def test_publish_response_loss_blocks_retry(self):
  draft=self.draft()
  def lost(url,*args,**kwargs):
   if url.endswith('/threads_publish'):raise app.Problem('timeout',502)
   return self.fake(url,*args,**kwargs)
  with patch.object(app,'remote',side_effect=lost):
   with self.assertRaises(app.Problem):app.threads_service().publish(draft['id'])
  with app.db() as db:self.assertEqual(db.execute('SELECT state FROM threads_attempts').fetchone()[0],'uncertain')
  self.calls=[]
  with patch.object(app,'remote',side_effect=self.fake):
   with self.assertRaises(app.Problem):app.threads_service().publish(draft['id'])
  self.assertFalse(any(body for _,body,_,_ in self.calls))
 def test_before_publish_failure_allows_retry_and_instagram_is_independent(self):
  draft=self.draft()
  with app.db() as db:db.execute('INSERT INTO attempts VALUES(?,?,?,?,?)',('ig',draft['id'],'published','{}',1))
  def bad(url,*args,**kwargs):
   if url.endswith('/threads'):raise app.Problem('bad media',502)
   return self.fake(url,*args,**kwargs)
  with patch.object(app,'remote',side_effect=bad):
   with self.assertRaises(app.Problem):app.threads_service().publish(draft['id'])
  with patch.object(app,'remote',side_effect=self.fake):app.threads_service().publish(draft['id'])
  with app.db() as db:self.assertEqual([row[0] for row in db.execute('SELECT state FROM threads_attempts ORDER BY created')],['failed','published'])
 def test_container_error_never_calls_publish(self):
  draft=self.draft()
  def bad(url,*args,**kwargs):
   if '?fields=status' in url:return {'status':'ERROR'}
   return self.fake(url,*args,**kwargs)
  with patch.object(app,'remote',side_effect=bad):
   with self.assertRaises(app.Problem):app.threads_service().publish(draft['id'])
  self.assertFalse(any(url.endswith('/threads_publish') for url,_,_,_ in self.calls))
 def test_configuration_no_token_leak_and_no_instagram_fallback(self):
  with patch.dict(os.environ,{'THREADS_ACCESS_TOKEN':''}):
   config=app.threads_service().configuration()
   self.assertFalse(config['ready']);self.assertIn('THREADS_ACCESS_TOKEN',config['missing'])
  self.assertNotIn('threads-test-only',json.dumps(config))

 def test_check_can_find_id_before_user_id_is_configured(self):
  with patch.dict(os.environ,{'THREADS_USER_ID':''}),patch.object(app,'remote',side_effect=self.fake):
   result=app.threads_service().check()
  self.assertEqual(result['user_id'],'777');self.assertFalse(result['account_matches'])

 def test_missing_token_and_invalid_version_have_distinct_messages(self):
  with patch.dict(os.environ,{'THREADS_ACCESS_TOKEN':''}):
   with self.assertRaisesRegex(app.Problem,'완전히 종료'):app.threads_service().graph('me?fields=id')
  with patch.dict(os.environ,{'THREADS_API_VERSION':'1.0'}):
   with self.assertRaisesRegex(app.Problem,'v1.0'):app.threads_service().graph('me?fields=id')
