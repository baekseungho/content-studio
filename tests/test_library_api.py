import json,tempfile,unittest,urllib.request,urllib.error
from pathlib import Path
from unittest.mock import patch
import app
import test_writing_api as writing_api

class LibraryAPITests(unittest.TestCase):
 call=writing_api.WritingAPITests.call
 def setUp(self):
  writing_api.WritingAPITests.setUp(self);self.data=patch.object(app,'DATA',Path(self.temp.name));self.data.start()
  with app.db() as conn:conn.execute('CREATE TABLE drafts(id TEXT PRIMARY KEY,title TEXT,data TEXT,updated REAL)')
  self.draft=app.save_draft({'title':'카페에서 보낸 오후','blog':'크림이 고소했던 라떼 이야기예요.','tistory':'','selective_generation':True,'selected_platforms':['naver']})
 def tearDown(self):writing_api.WritingAPITests.tearDown(self);self.data.stop()
 def test_library_page_and_single_card_are_safe(self):
  status,result=self.call('/api/library?limit=1');self.assertEqual(status,200);self.assertEqual(result['total'],1);self.assertNotIn('blog',result['items'][0]);self.assertEqual(result['items'][0]['channel_states']['naver']['state'],'draft')
  self.assertEqual(self.call('/api/library/story/'+self.draft['id'])[0],200)
 def test_explicit_review_is_local_and_optimistic(self):
  with patch.object(app,'remote',side_effect=AssertionError('Unexpected AI')):
   status,_=self.call('/api/library/review',{'id':self.draft['id'],'updated':self.draft['updated'],'platform':'naver','confirmed':True})
  self.assertEqual(status,200);self.assertFalse(app.JOBS);self.assertTrue(self.call('/api/library/story/'+self.draft['id'])[1]['channel_states']['naver']['reviewed'])
  status,_=self.call('/api/library/review',{'id':self.draft['id'],'updated':0,'platform':'naver','confirmed':True});self.assertEqual(status,409)
 def test_metadata_conflict_is_specific_and_keeps_first_value(self):
  body={'id':self.draft['id'],'revision':0,'changes':{'label':'원래 저장한 이름'}};self.assertEqual(self.call('/api/library/meta',body)[0],200)
  status,result=self.call('/api/library/meta',{**body,'changes':{'label':'낡은 수정'}});self.assertEqual(status,409);self.assertEqual(result['code'],'library_conflict');self.assertEqual(self.call('/api/library/story/'+self.draft['id'])[1]['story_title'],'원래 저장한 이름')
 def test_kit_preview_does_not_save_or_call_ai(self):
  with patch.object(app,'remote',side_effect=AssertionError('Unexpected AI')):
   status,kit=self.call('/api/kits',{'kind':'tags','name':'산책 태그','settings':{'hashtags':'#산책 #기록'}});self.assertEqual(status,200)
   status,result=self.call('/api/kits/preview',{'id':kit['id'],'revision':1,'current':{'hashtags':'#기존'},'groups':['tags']})
  self.assertEqual(status,200);self.assertEqual(result['patch']['hashtags'],'#기존 #산책 #기록');self.assertEqual(app.get_draft(self.draft['id'])['blog'],self.draft['blog']);self.assertFalse(app.JOBS)
 def test_kit_archive_can_be_restored(self):
  _,kit=self.call('/api/kits',{'kind':'tags','name':'카페 태그','settings':{'hashtags':'#카페'}});self.call('/api/kits/archive',{'id':kit['id'],'revision':1});self.assertEqual(self.call('/api/kits')[1],[]);old=self.call('/api/kits?archived=1')[1][0];self.assertEqual(self.call('/api/kits',old)[0],200);self.assertEqual(len(self.call('/api/kits')[1]),1)
 def test_damaged_story_has_explanatory_response(self):
  with app.db() as conn:conn.execute('INSERT INTO drafts VALUES(?,?,?,?)',('d'*32,'문제 있는 원고','broken',100))
  self.assertEqual(self.call('/api/library')[1]['total'],2);status,result=self.call('/api/drafts/'+'d'*32);self.assertEqual(status,409);self.assertIn('원본',result['error'])
 def test_private_thumbnail_is_small_and_keeps_original(self):
  from PIL import Image
  import io
  root=Path(self.temp.name)/'thumb-media';root.mkdir();mid='a'*32;source=root/(mid+'.jpg');Image.new('RGB',(1600,1000),'red').save(source);original=source.read_bytes()
  with patch.object(app,'MEDIA',root),patch.object(app,'remote',side_effect=AssertionError('Unexpected AI')):
   with urllib.request.urlopen(self.base+'/api/library/thumb/'+mid) as response:
    self.assertTrue(response.headers['Content-Type'].startswith('image/jpeg'));payload=response.read()
  with Image.open(io.BytesIO(payload)) as image:self.assertEqual(image.size,(200,200))
  self.assertEqual(source.read_bytes(),original);self.assertEqual(len(list(root.iterdir())),1)
 def test_mutations_require_app_token(self):
  for path in ('/api/library/meta','/api/library/review','/api/library/open','/api/kits','/api/kits/archive','/api/kits/preview'):
   request=urllib.request.Request(self.base+path,data=b'',method='POST')
   with self.subTest(path=path),self.assertRaises(urllib.error.HTTPError) as caught:urllib.request.urlopen(request)
   self.assertEqual(caught.exception.code,403)

if __name__=='__main__':unittest.main()
