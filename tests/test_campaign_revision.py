import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import app
from campaigns import read_fields,writing_context,character_count,mission_checks
from platform_writing import instructions_for

def response(value):return {"output":[{"type":"message","content":[{"type":"output_text","text":json.dumps(value,ensure_ascii=False)}]}]}

class CampaignRevisionTests(unittest.TestCase):
 def test_optional_min_max_and_counting(self):
  self.assertEqual(read_fields({})['campaign_max_chars'],0)
  self.assertEqual(character_count('## Heading\nAB CD\n[[photo:1]]\n#tag'),11)
  self.assertEqual(character_count('AB CD\nEF',True),7)
  with self.assertRaisesRegex(ValueError,'최소'):read_fields({'campaign_min_chars':100,'campaign_max_chars':50})
  with self.assertRaises(ValueError):read_fields({'campaign_count_spaces':'yes'})
  self.assertEqual(writing_context({'campaign_max_chars':100})['campaign_max_chars'],0)
 def test_length_errors_have_actionable_targets(self):
  checks=mission_checks({'campaign_enabled':True,'blog':'짧은 글','campaign_min_chars':100,'campaign_max_chars':2,'disclosure':'paid'})
  for field in ('campaign_min_chars','campaign_max_chars'):
   found=next(c for c in checks if c['field']==field);self.assertFalse(found['passed']);self.assertEqual(found['target'],'body');self.assertIn('현재',found['detail'])
 def test_keyword_duplicates_are_not_independent_errors(self):
  checks=mission_checks({'campaign_enabled':True,'title':'성수 카페','blog':'성수 카페','title_keywords':'성수카페, 성수 카페','body_keywords':'성수카페','disclosure':'paid'})
  self.assertTrue(all(c['passed'] for c in checks));self.assertEqual(len([c for c in checks if c['field']=='title_keywords']),1)
 def test_review_retains_field_and_reason(self):
  checks=app.review({'campaign_enabled':True,'title':'후기','blog':'내용','title_keywords':'필수키워드','disclosure':'paid'})
  issue=next(c for c in checks if c.get('field')=='title_keywords')
  self.assertEqual(issue['target'],'title');self.assertIn('제목에 이 키워드가 없어요',issue['message'])
 def test_english_conflict_does_not_silently_translate_mission(self):
  checks=mission_checks({'campaign_enabled':True,'language':'en','title':'Cafe','blog':'A coffee break.','title_keywords':'성수맛집','disclosure':'paid'})
  item=next(c for c in checks if c['field']=='title_keywords');self.assertIn('영문 표기',item['detail']);self.assertFalse(item['passed'])
 def test_english_regeneration_does_not_reinsert_korean_tags_when_saved(self):
  answer={'title':'A coffee break','blog':"I liked the cream on this one. It had a nutty taste."}
  request={'platforms':['naver'],'prompt':'크림이 고소했어','language':'en','images':[],'hashtags':'#성수카페 #Coffee','blog':'기존 한국어 원고','title':'예전 제목','tone':'담백하고 차분하게'}
  with patch.dict(os.environ,{'OPENAI_API_KEY':'test'}),patch.object(app,'remote',return_value=response(answer)) as remote:
   generated=app.generate(request)
  self.assertNotIn('기존 한국어 원고',json.dumps(remote.call_args.args[1],ensure_ascii=False));self.assertNotIn('#성수카페',generated['blog']);self.assertIn('#Coffee',generated['blog'])
  with tempfile.TemporaryDirectory() as folder,patch.object(app,'DATA',Path(folder)):
   with app.db() as c:c.execute('CREATE TABLE drafts(id TEXT PRIMARY KEY,title TEXT,data TEXT,updated REAL)')
   saved=app.save_draft({**request,**generated,'editing_platform':'naver','platform_languages':{'naver':'en'}})
   self.assertNotIn('#성수카페',saved['blog']);self.assertEqual(saved['blog'],generated['blog'])
 def test_mixed_english_result_fails_before_replacing_previous_draft(self):
  with patch.dict(os.environ,{'OPENAI_API_KEY':'test'}),patch.object(app,'remote',return_value=response({'threads':'A quiet moment. 좋았어.'})):
   with self.assertRaisesRegex(app.Problem,'한국어가 남아'):app.generate({'platforms':['threads'],'prompt':'기록','language':'en','images':[]})
 def test_english_prompt_is_conversational_and_length_aware(self):
  guide=instructions_for(['naver'],'en',{'campaign_enabled':True})
  self.assertIn('telling a friend',guide);self.assertIn('campaign_max_chars',guide);self.assertIn('Do not insert Korean mission',guide)

 def test_case_only_difference_does_not_append_duplicate_english_fact(self):
  from writing_quality import required_instagram_story
  caption="The cream tasted nutty."
  self.assertEqual(required_instagram_story(caption,"the cream tasted nutty."),caption)
