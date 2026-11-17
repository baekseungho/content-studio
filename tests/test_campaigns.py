import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import app
from campaigns import read_fields,tags_from,apply_tags,mission_checks,count_keyword,community_guidance,writing_context
from extension_bridge import ExtensionBridge,HandoffError
from naver_guard import NaverGuard

class CampaignTests(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name);self.p=patch.object(app,'DATA',self.root);self.p.start()
  with app.db() as db:db.execute('CREATE TABLE drafts(id TEXT PRIMARY KEY,title TEXT,data TEXT,updated REAL)')
 def tearDown(self):self.p.stop();self.temp.cleanup()
 def test_validation_tags_and_counts(self):
  self.assertEqual(tags_from('#성수맛집, #성수맛집 #Coffee'),['성수맛집','Coffee'])
  self.assertEqual(count_keyword('성수 카페에서\n성수카페를','성수카페'),2)
  self.assertEqual(count_keyword('barista at a bar','bar'),1)
  for data in [{'campaign_enabled':'yes'},{'hashtags':'<script>'},{'keyword_min_count':0},{'campaign_min_photos':11},{'campaign_min_chars':True}]:
   with self.subTest(data=data),self.assertRaises(ValueError):read_fields(data)
 def test_save_roundtrip_and_managed_tag_removal(self):
  saved=app.save_draft({'title':'성수 카페 후기','blog':'본문','hashtags':'#성수 #카페','campaign_enabled':True,'campaign_brief':'업체 원문','threads_community':True,'threads_networking':True,'disclosure':'experience'})
  self.assertTrue(saved['blog'].endswith('#성수 #카페'))
  self.assertTrue(saved['blog'].startswith('식사 또는 이용권'))
  self.assertEqual(app.get_draft(saved['id'])['campaign_brief'],'업체 원문')
  again=app.save_draft(saved);self.assertEqual(again['blog'],saved['blog'])
  removed=app.save_draft({**again,'hashtags':''});self.assertNotIn('#성수',removed['blog'])
 def test_hashtags_do_not_count_as_body_keywords_and_phrase_match(self):
  draft={'campaign_enabled':True,'title':'후기','blog':'다른 내용\n#성수맛집','body_keywords':'성수맛집','keyword_min_count':1,'required_phrases':'서비스가 친절했어요.','hashtags':'성수맛집','disclosure':'gifted'}
  checks=mission_checks(draft)
  self.assertFalse(next(c for c in checks if c['label'].startswith('본문'))['passed'])
  self.assertFalse(next(c for c in checks if c['label'].startswith('필수'))['passed'])
  self.assertTrue(next(c for c in checks if c['label'].startswith('태그'))['passed'])
  draft['blog']='성수 맛집에서\n서비스가\n친절했어요.\n#성수맛집'
  self.assertTrue(all(c['passed'] for c in mission_checks(draft)))
 def test_missing_mission_blocks_handoff_and_complete_passes(self):
  bridge=ExtensionBridge(self.root,NaverGuard(self.root/'guard.json'))
  draft={'id':'a'*32,'title':'후기','blog':'본문','images':[],'campaign_enabled':True,'title_keywords':'성수카페','disclosure':'gifted'}
  with self.assertRaisesRegex(HandoffError,'체험단'):bridge.create(draft)
  result=bridge.create({**draft,'title':'성수카페 후기'});self.assertIn('code',result)
 def test_generation_and_polish_receive_campaign_and_community_preferences(self):
  answer={'title':'성수카페 샘플카페 후기','blog':'성수카페에서 마신 라테.','instagram':'카페 기록','threads':'스친들, 라테 위 크림 좋아해?\n나 이런 고소한 맛 좋아하더라.','sources':[]}
  response={'output':[{'type':'message','content':[{'type':'output_text','text':json.dumps(answer,ensure_ascii=False)}]}]}
  request={'prompt':'고소한 라테가 좋았어','images':[],'tone':'밝고 자연스러운 일상 후기체','campaign_enabled':True,'campaign_brand':'샘플카페','campaign_brief':'업체 안내','title_keywords':'성수카페','body_keywords':'성수카페','hashtags':'#성수카페','threads_community':True,'threads_networking':True,'disclosure':'experience'}
  with patch.dict(os.environ,{'OPENAI_API_KEY':'test'}),patch.object(app,'remote',return_value=response) as remote:
   generated=app.generate(request)
  self.assertEqual(remote.call_count,2)
  for call in remote.call_args_list:
   payload=call.args[1]
   self.assertIn('업체 미션',payload['instructions']);self.assertIn('소통 표현을 선택',payload['instructions'])
   context=json.loads(payload['input'][0]['content'][0]['text']);self.assertEqual(context['campaign_brand'],'샘플카페')
  self.assertTrue(generated['blog'].endswith('#성수카페'))
  self.assertTrue(all(item['passed'] for item in generated['campaign_checks']))
 def test_english_does_not_transliterate_korean_community_terms(self):
  guide=community_guidance({'language':'en','threads_community':True,'threads_networking':True})
  self.assertIn('never transliterate',guide)

 def test_turning_campaign_off_keeps_metadata_but_hides_it_from_model(self):
  request={'campaign_enabled':False,'campaign_brief':'반영하면 안 되는 이전 미션','title_keywords':'이전키워드','hashtags':'#현재태그'}
  context=writing_context(request)
  self.assertEqual(context['campaign_brief'],'');self.assertEqual(context['title_keywords'],'');self.assertEqual(context['hashtags'],'#현재태그')
  self.assertEqual(read_fields(request)['campaign_brief'],request['campaign_brief'])

 def test_managed_tags_are_not_duplicated_when_photo_markers_move_after_them(self):
  body="본문\n\n#성수카페\n\n[[photo:2]]"
  result=apply_tags(body,['성수카페'],['성수카페'])
  self.assertEqual(result.count('#성수카페'),1)
  self.assertTrue(result.endswith('#성수카페'))
  self.assertIn('[[photo:2]]',result)

 def test_disclosure_can_be_fixed_on_existing_text_without_regeneration(self):
  initial=app.save_draft({'title':'내가 쓴 후기','blog':'원래 후기 본문','instagram':'원래 캡션','threads':'원래 짧은 글','campaign_enabled':True})
  missing=next(c for c in mission_checks(initial) if c['label']=='광고·제공 표시')
  self.assertFalse(missing['passed']);self.assertIn('직접 구매',missing['detail'])
  updated=app.save_draft({**initial,'disclosure':'experience'})
  self.assertTrue(updated['blog'].startswith('식사 또는 이용권을 제공받아 작성한 글입니다.'))
  self.assertIn('원래 후기 본문',updated['blog'])
  self.assertTrue(all(c['passed'] for c in mission_checks(updated)))
