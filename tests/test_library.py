import json,unittest
import app

class LibraryTests(unittest.TestCase):
 def summary(self,data):return app.draft_summary({'id':'a'*32,'title':'','data':json.dumps(data),'updated':1000})
 def test_social_only_story_has_a_readable_title_and_channel(self):
  summary=self.summary({'threads':'오늘의 작은 기록.','images':[]})
  self.assertEqual(summary['title'],'오늘의 작은 기록.');self.assertEqual(summary['platforms'],['threads'])
 def test_cards_include_only_safe_small_metadata(self):
  summary=self.summary({'title':'카페','blog':'긴 문장 '*200,'images':['../private','b'*32],'selected_place':{'name':'성수 카페'},'access_token':'never expose'})
  self.assertEqual(summary['thumbnail'],'b'*32);self.assertEqual(summary['place'],'성수 카페');self.assertLessEqual(len(summary['excerpt']),140)
  self.assertNotIn('access_token',summary);self.assertNotIn('blog',summary);self.assertEqual(summary['photo_count'],2)
 def test_legacy_shared_blogs_and_independent_blogs_are_distinguished(self):
  self.assertEqual(self.summary({'blog':'구버전 본문'})['platforms'],['naver','tistory'])
  self.assertEqual(self.summary({'blog':'네이버 원고','tistory':''})['platforms'],['naver'])
 def test_summary_strips_photo_markers_and_handles_untitled_notes(self):
  summary=self.summary({'prompt':'아직 원고로 만들지 않은 메모','blog':'','tistory':''})
  self.assertIn('아직 원고',summary['title']);self.assertEqual(summary['platforms'],[])
  self.assertNotIn('photo:',self.summary({'blog':'본문 [[photo:1]] #태그'})['excerpt'])

 def test_independent_tistory_title_is_available_to_library_search(self):
  summary=self.summary({'title':'네이버 제목','blog':'네이버 글','tistory_title':'다른 티스토리 제목','tistory':'티스토리 글'})
  self.assertIn('다른 티스토리 제목',summary['titles']);self.assertEqual(summary['platforms'],['naver','tistory'])
