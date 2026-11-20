"""User assertions are explicit, canonical, revision-bound and separate from API verification."""
import json,unittest,urllib.request
from pathlib import Path
from unittest.mock import patch
import app,publication_records as records
import test_writing_api as api_fixture

class PublicationURLTests(unittest.TestCase):
 def test_naver_desktop_mobile_and_legacy_urls_are_canonical(self):
  expected='https://blog.naver.com/sample_blog/224123456789'
  for value in (expected,expected+'?trackingCode=test',expected.replace('blog.naver','m.blog.naver')+'#comment','https://m.blog.naver.com/PostView.naver?blogId=sample_blog&logNo=224123456789&trackingCode=test'):
   self.assertEqual(records.canonical_url(value,'naver'),expected)
 def test_tistory_numeric_and_utf8_slug_are_canonical(self):
  self.assertEqual(records.canonical_url('https://sample.tistory.com/12?category=1','tistory'),'https://sample.tistory.com/12')
  for value in ('https://sample.tistory.com/entry/우리 동네 후기','https://sample.tistory.com/entry/%EC%9A%B0%EB%A6%AC%20%EB%8F%99%EB%84%A4%20%ED%9B%84%EA%B8%B0'):
   self.assertEqual(records.canonical_url(value,'tistory'),'https://sample.tistory.com/entry/%EC%9A%B0%EB%A6%AC%20%EB%8F%99%EB%84%A4%20%ED%9B%84%EA%B8%B0')
 def test_management_private_and_hostile_urls_are_rejected(self):
  cases=[('naver',u) for u in ('javascript:alert(1)','http://blog.naver.com/user/1','https://blog.naver.com.evil.test/user/1','https://user@blog.naver.com/user/1','https://blog.naver.com:443/user/1','https://blog.naver.com/user?Redirect=Write','https://blog.naver.com/PostList.naver?blogId=user','https://blog.naver.com/PostView.naver?blogId=user&logNo=1&logNo=2','https://blog.naver.com/user/1?access_token=secret','https://127.0.0.1/user/1')]
  cases += [('tistory',u) for u in ('https://sample.tistory.com/manage/newpost/','https://sample.tistory.com/1?previewMode=true','https://sample.tistory.com/1?secret=x','https://sample.tistory.com/entry/../manage','https://sample.tistory.com/entry/%0Atest','https://sample.tistory.com/entry/%xx','https://sample.tistory.com/entry/a%2Fb','https://www.tistory.com/1','https://sample.tistory.com/')]
  for platform,value in cases:
   with self.subTest(url=value),self.assertRaises(ValueError):records.canonical_url(value,platform)
 def test_wrong_blog_and_nonstring_inputs_are_rejected(self):
  with self.assertRaisesRegex(ValueError,'다른 블로그'):records.canonical_url('https://blog.naver.com/other/1','naver','mine')
  with self.assertRaisesRegex(ValueError,'다른 블로그'):records.canonical_url('https://other.tistory.com/1','tistory',blog_url='https://mine.tistory.com')
  for value in (None,[],{},1):
   with self.assertRaises(ValueError):records.canonical_url(value,'naver')

class PublicationAPITests(unittest.TestCase):
 call=api_fixture.WritingAPITests.call
 def setUp(self):
  api_fixture.WritingAPITests.setUp(self);self.patches=[patch.object(app,'DATA',Path(self.temp.name)),patch.dict(app.os.environ,{'NAVER_BLOG_ID':'sample_blog'})]
  for p in self.patches:p.start()
  with app.db() as conn:conn.execute('CREATE TABLE drafts(id TEXT PRIMARY KEY,title TEXT,data TEXT,updated REAL)')
  self.draft=app.save_draft({'title':'직접 발행한 카페 후기','blog':'창가에서 쉬고 라떼를 마셨어요.','selective_generation':True,'selected_platforms':['naver'],'editing_platform':'naver'})
 def tearDown(self):
  for p in reversed(self.patches):p.stop()
  api_fixture.WritingAPITests.tearDown(self)
 def body(self,**extra):return {'id':self.draft['id'],'updated':self.draft['updated'],'platform':'naver','url':'https://m.blog.naver.com/sample_blog/224123456789?trackingCode=test','confirmed':True,**extra}
 def card(self):return app.library.story_card(app.db,app.draft_summary,self.draft['id'])
 def test_auth_is_required_before_record_or_validation(self):
  for path in ('/api/publications','/api/publications/preview','/api/publications/archive'):
   self.assertEqual(self.call(path,self.body(),False)[0],403)
 def test_preview_has_no_record_write_or_external_calls(self):
  with patch.object(app,'remote',side_effect=AssertionError('No external calls')):
   status,value=self.call('/api/publications/preview',self.body())
  self.assertEqual(status,200);self.assertEqual(value['verification'],'not_fetched');self.assertEqual(value['url'],'https://blog.naver.com/sample_blog/224123456789');self.assertEqual(self.call('/api/publications')[1],[]);self.assertFalse(app.JOBS)
 def test_explicit_confirmation_and_saved_revision_are_required(self):
  for confirmed in (False,None,1,'true'):self.assertEqual(self.call('/api/publications',self.body(confirmed=confirmed))[0],400)
  for value in (None,True,'1'):self.assertEqual(self.call('/api/publications',self.body(updated=value))[0],400)
  self.assertEqual(self.call('/api/publications')[1],[])
 def test_stale_revision_rejected_without_changing_original(self):
  status,value=self.call('/api/publications',self.body(updated=0));self.assertEqual(status,409);self.assertEqual(value['code'],'publication_conflict');self.assertEqual(app.get_draft(self.draft['id'])['blog'],self.draft['blog']);self.assertEqual(self.call('/api/publications')[1],[])
 def test_record_is_user_confirmed_idempotent_and_draft_is_untouched(self):
  before=app.get_draft(self.draft['id'])
  with patch.object(app,'remote',side_effect=AssertionError('No external calls')):
   status,one=self.call('/api/publications',self.body());_,two=self.call('/api/publications',self.body())
  self.assertEqual(status,200);self.assertEqual(one,two);self.assertEqual(one['verification'],'user_confirmed');self.assertEqual(app.get_draft(self.draft['id']),before);self.assertEqual(len(self.call('/api/publications')[1]),1);self.assertFalse(app.JOBS)
  state=self.card()['channel_states']['naver'];self.assertEqual(state['state'],'published');self.assertEqual(state['verification'],'user_confirmed');self.assertFalse(state['reviewed']);self.assertEqual(self.card()['state'],'published')
 def test_later_edit_is_not_marked_as_current_publication(self):
  self.call('/api/publications',self.body());app.save_draft({**self.draft,'blog':'이번에 새로 고친 원고예요.'});state=self.card()['channel_states']['naver'];self.assertEqual(state['state'],'changed');self.assertIn('이전 원고',state['label']);self.assertFalse(self.call('/api/publications')[1][0]['matches_current']);self.assertEqual(self.card()['state'],'attention')
 def test_missing_current_text_keeps_old_publication_address(self):
  self.call('/api/publications',self.body());app.save_draft({**self.draft,'blog':'','blog_documents':{},'selected_platforms':[]});state=self.card()['channel_states']['naver'];self.assertEqual(state['state'],'changed');self.assertIn('현재 원고 없음',state['label']);self.assertIn('published_url',state)
 def test_archive_restore_and_conflict_preserve_post_and_draft(self):
  _,record=self.call('/api/publications',self.body());body={'record_id':record['id'],'revision':record['revision'],'archived':True};self.assertEqual(self.call('/api/publications/archive',body)[0],200);self.assertEqual(self.call('/api/publications')[1],[]);self.assertEqual(self.card()['channel_states']['naver']['state'],'draft');self.assertEqual(self.call('/api/publications/archive',body)[0],409)
  archived=self.call('/api/publications?archived=1')[1][0];self.assertEqual(self.call('/api/publications/archive',{'record_id':archived['id'],'revision':archived['revision'],'archived':False})[0],200);self.assertEqual(self.card()['channel_states']['naver']['state'],'published');self.assertEqual(app.get_draft(self.draft['id'])['blog'],self.draft['blog'])
 def test_readding_archived_address_restores_without_duplicate(self):
  _,record=self.call('/api/publications',self.body());self.call('/api/publications/archive',{'record_id':record['id'],'revision':record['revision'],'archived':True});_,restored=self.call('/api/publications',self.body());self.assertEqual(restored['id'],record['id']);self.assertFalse(restored['archived']);self.assertEqual(len(self.call('/api/publications')[1]),1)
 def test_wrong_blog_or_unsupported_channel_cannot_be_recorded(self):
  for extra in ({'url':'https://blog.naver.com/other/1'},{'platform':'instagram'},{'platform':'tistory','url':'https://other.tistory.com/1','blog_url':'https://mine.tistory.com'}):self.assertEqual(self.call('/api/publications',self.body(**extra))[0],400)
 def test_tistory_record_is_separate_from_naver(self):
  self.draft=app.save_draft({**self.draft,'tistory_title':'티스토리 후기','tistory':'티스토리의 별도 원고예요.','selected_platforms':['naver','tistory']});self.call('/api/publications',self.body());self.assertEqual(self.call('/api/publications',self.body(platform='tistory',url='https://mine.tistory.com/1',blog_url='https://mine.tistory.com'))[0],200);states=self.card()['channel_states'];self.assertEqual(states['naver']['state'],'published');self.assertEqual(states['tistory']['state'],'published')
 def test_unsafe_database_address_is_not_exposed_as_a_link(self):
  self.call('/api/publications',self.body())
  with app.db() as conn:conn.execute("UPDATE publication_records SET url='javascript:alert(1)'")
  self.assertEqual(self.call('/api/publications')[1],[]);self.assertNotIn('published_url',self.card()['channel_states']['naver'])

 def test_damaged_draft_does_not_hide_safe_publication_address(self):
  self.call('/api/publications',self.body())
  with app.db() as conn:conn.execute('UPDATE drafts SET data=? WHERE id=?',('broken',self.draft['id']))
  rows=self.call('/api/publications')[1];self.assertEqual(len(rows),1);self.assertTrue(rows[0]['draft_unreadable']);self.assertFalse(rows[0]['matches_current']);self.assertEqual(rows[0]['url'],'https://blog.naver.com/sample_blog/224123456789')
 def test_overlong_encoded_address_is_rejected_before_recording(self):
  status,_=self.call('/api/publications/preview',self.body(platform='tistory',url='https://mine.tistory.com/entry/'+'가'*400));self.assertEqual(status,400);self.assertEqual(self.call('/api/publications')[1],[])

 def test_simultaneous_confirmation_creates_one_record(self):
  from concurrent.futures import ThreadPoolExecutor
  with ThreadPoolExecutor(max_workers=2) as pool:results=list(pool.map(lambda _:self.call('/api/publications',self.body()),range(2)))
  self.assertEqual([status for status,_ in results],[200,200]);self.assertEqual(len({value['id'] for _,value in results}),1);self.assertEqual(len(self.call('/api/publications')[1]),1)
