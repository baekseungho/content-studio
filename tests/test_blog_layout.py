import json,os,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
import app
from blog_layout import settings,all_settings,reflow
class BlogLayoutTests(unittest.TestCase):
 def test_manual_preserves_exact_text(self):
  value="제목\n\n한 줄\n두 줄\n\n[[photo:1]]"
  self.assertEqual(reflow(value),value)
 def test_word_order_markers_and_special_lines_survive(self):
  value="## 제목\n\n오늘은 사진 사이에 여백을 두고 편안하게 이야기를 적어 보고 싶어요. 짧은 문장을 천천히 읽을 수 있도록 글의 호흡을 나눠요.\n\n[[photo:1]]\n\n주소: 서울특별시 성동구 성수일로 123\n\n#성수카페 #일상"
  result=reflow(value,{'preset':'notes'})
  self.assertEqual(result.split(),value.split());self.assertEqual(result.count('[[photo:1]]'),1)
  self.assertIn('주소: 서울특별시 성동구 성수일로 123',result);self.assertTrue(result.endswith('#성수카페 #일상'))
  self.assertEqual(reflow(result,{'preset':'notes'}),result)
 def test_long_words_and_english_are_not_cut(self):
  value='A small observation with an unusuallylongwordthatmuststayintact and a little space to breathe between thoughts.'
  result=reflow(value,{'preset':'notes'},'en');self.assertEqual(result.split(),value.split())
 def test_validation(self):
  for value in ({'preset':'bad'},{'width':True},{'width':15},{'lines':7},[]):
   with self.subTest(value=value),self.assertRaises(ValueError):settings(value)
  with self.assertRaises(ValueError):all_settings({'instagram':{}})
 def test_settings_and_original_roundtrip(self):
  with tempfile.TemporaryDirectory() as folder,patch.object(app,'DATA',Path(folder)):
   with app.db() as c:c.execute('CREATE TABLE drafts(id TEXT PRIMARY KEY,title TEXT,data TEXT,updated REAL)')
   source='한 문장을 조금 길게 써서 줄을 나눠 보고 싶은 날의 이야기예요.'
   saved=app.save_draft({'title':'제목','blog':reflow(source,{'preset':'notes'}),'blog_layouts':{'naver':{'preset':'notes'}},'layout_bases':{'naver':source},'layout_last':{'naver':reflow(source,{'preset':'notes'})}})
   loaded=app.get_draft(saved['id']);self.assertEqual(loaded['layout_bases']['naver'],source);self.assertEqual(loaded['blog_layouts']['naver']['width'],20)
 def test_selected_generation_applies_only_selected_blog_layout(self):
  value='오늘의 작은 이야기를 차근차근 남기고 싶었어요. 사진 사이에는 여백도 조금 두고 편안한 호흡으로 글을 읽고 싶었어요.'
  response={'output':[{'type':'message','content':[{'type':'output_text','text':json.dumps({'tistory_title':'제목','tistory':value})}]}]}
  with patch.dict(os.environ,{'OPENAI_API_KEY':'test'}),patch.object(app,'remote',return_value=response) as remote:
   result=app.generate({'platforms':['tistory'],'prompt':'글','tone':'담백하고 차분하게','blog_layouts':{'tistory':{'preset':'notes'}},'images':[]})
  self.assertEqual(remote.call_count,1);self.assertIn('\n',result['tistory']);self.assertEqual(result['layout_last']['tistory'],result['tistory']);self.assertNotIn('blog',result)

 def test_layout_never_silently_exceeds_storage_limit(self):
  with self.assertRaisesRegex(ValueError,'30,000'):reflow('abc '*7400,{'preset':'custom','width':16,'lines':2})
