"""Local merchant brief extraction and conflict checks; no AI calls."""
import copy,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
import app
from campaign_brief import extract,digest
from campaign_requirements import preflight,read_meta,report
from campaigns import mission_checks,writing_context

class BriefTests(unittest.TestCase):
 def values(self,text,field):return [x['value'] for x in extract(text)['suggestions'] if x['field']==field and x['kind']=='condition']
 def test_common_guide_has_exact_evidence_and_does_not_select_for_user(self):
  text='안내 🌸\n업체명: 메모카페\n제목 키워드: 성수카페, 메모카페\n본문 키워드: 크림라떼 (각 3회 이상)\n본문: 공백 제외 2,000~3,000자\n사진 5장 이상\n해시태그: #성수 #카페\n지도와 배너를 넣어 주세요.'
  result=extract(text)
  for item in result['suggestions']:self.assertEqual(text[item['start']:item['end']],item['quote'])
  self.assertEqual(self.values(text,'campaign_min_chars'),[2000]);self.assertEqual(self.values(text,'campaign_max_chars'),[3000]);self.assertEqual(self.values(text,'campaign_count_spaces'),[False]);self.assertEqual(self.values(text,'keyword_min_count'),[3]);self.assertEqual(self.values(text,'body_keywords'),['크림라떼'])
 def test_strict_limits_and_korean_units(self):
  self.assertEqual(self.values('본문 최소 2천5백 자','campaign_min_chars'),[2500]);self.assertEqual(self.values('2천500자 초과','campaign_min_chars'),[2501]);self.assertEqual(self.values('본문 3,000자 미만','campaign_max_chars'),[2999])
 def test_unsupported_length_is_manual_without_silent_clamping(self):
  item=extract('본문 6,000자 이상')['suggestions'][0];self.assertEqual(item['kind'],'manual');self.assertEqual(item['value'],6000)
 def test_photo_ranges_do_not_become_wrong_minimum(self):
  self.assertEqual(self.values('사진 5~10장','campaign_min_photos'),[5]);self.assertEqual(self.values('사진 3~6장','campaign_min_photos'),[3]);self.assertTrue(any(x['kind']=='manual' for x in extract('사진 3~6장')['suggestions']))
 def test_choices_are_never_auto_selected(self):
  result=extract('제목 키워드: 성수카페, 서울카페 중 1개 선택');self.assertTrue(all(x['kind']=='manual' for x in result['suggestions']))
 def test_instagram_limits_are_not_blog_limits(self):
  result=extract('[인스타그램]\n본문 300자 이상\n[블로그]\n본문 2000자 이상');self.assertEqual([x['value'] for x in result['suggestions'] if x['field']=='campaign_min_chars'],[2000])
 def test_title_lengths_and_literal_phrases_are_not_body_rules(self):
  self.assertFalse(self.values('제목 30자 이내','campaign_max_chars'));self.assertFalse(self.values('필수 문구: 사진 5장 이상을 권장합니다.','campaign_min_photos'))
 def test_keywords_containing_usage_are_not_truncated(self):self.assertEqual(self.values('본문 키워드: 제품사용감, 사용후기','body_keywords'),['제품사용감, 사용후기'])
 def test_advertising_phrase_and_links_are_manual(self):
  self.assertTrue(all(x['kind']=='manual' for x in extract('필수 문구: 제품을 제공받아 작성했습니다.\n링크: https://example.com')['suggestions']))
 def test_exact_count_is_not_part_of_keyword_and_is_left_for_manual_review(self):
  rows=extract('본문 키워드: 커피 정확히 3회')['suggestions'];self.assertEqual(next(x['value'] for x in rows if x['field']=='body_keywords'),'커피');self.assertTrue(any(x['kind']=='manual' for x in rows))
 def test_no_blank_or_oversized_input(self):
  for text in ('','x'*5001,None):
   with self.assertRaises(ValueError):extract(text)

class RequirementTests(unittest.TestCase):
 def base(self,**extra):return {'campaign_enabled':True,'disclosure':'experience','campaign_brief':'지도 첨부','title':'카페 후기','blog':'실제 경험','images':[],**extra}
 def test_impossible_length_and_forbidden_conditions_are_explained(self):
  issues=preflight(self.base(campaign_min_chars=2000,campaign_max_chars=1000,title_keywords='최고의 카페',campaign_forbidden='최고'))
  self.assertTrue(any(i['code']=='campaign_length_conflict' and 'campaign_max_chars' in i['related_fields'] for i in issues));self.assertTrue(any(i['code']=='campaign_forbidden_conflict' for i in issues))
 def test_invalid_tag_points_to_tag_field(self):self.assertTrue(any(i['field']=='hashtags' for i in preflight(self.base(hashtags='<bad>'))))
 def test_provided_review_cannot_require_self_paid_claim(self):self.assertTrue(any(i['code']=='campaign_disclosure_conflict' for i in preflight(self.base(required_phrases='내돈내산 후기예요.'))))
 def test_reviewed_brief_is_not_sent_back_to_model_as_unconfirmed_instructions(self):
  body=self.base(campaign_brief_review={'hash':digest('지도 첨부'),'sources':[]},body_keywords='커피');context=writing_context(body);self.assertEqual(context['campaign_brief'],'');self.assertEqual(context['body_keywords'],'커피')
 def test_changed_guide_requires_review_and_paused_personal_mode_ignores_it(self):
  body=self.base(campaign_brief_review={'hash':digest('이전 안내'),'sources':[]});self.assertTrue(any(i['code']=='campaign_brief_changed' for i in preflight(body)));self.assertEqual(preflight({**body,'campaign_enabled':False}),[])
 def test_actual_forbidden_word_has_location(self):
  row=next(x for x in mission_checks(self.base(blog='여기는 최 고예요.',campaign_forbidden='최고')) if x['field']=='campaign_forbidden');self.assertFalse(row['passed']);self.assertEqual(row['target'],'body');self.assertEqual(row['needle'],'최고')
 def test_manual_checks_are_scoped_and_invalidated_after_edit(self):
  item={'id':'a'*20,'text':'지도 확인','quote':'지도 첨부'};body=self.base(campaign_manual_checks=[item]);first=report(body)
  body['campaign_manual_state']={'naver':{item['id']:first['fingerprint']}};self.assertTrue(report(body)['manual'][0]['checked']);self.assertFalse(report(body,'tistory')['manual'][0]['checked']);self.assertFalse(report({**body,'blog':'바뀐 원고'})['manual'][0]['checked'])
 def test_bad_metadata_is_rejected(self):
  for body in ({'campaign_manual_checks':[{'id':'../../x','text':'bad'}]},{'campaign_manual_state':{'instagram':{}}},{'campaign_experience':{'good':'x'*601}}):
   with self.assertRaises(ValueError):read_meta(body)
 def test_preflight_conflict_refuses_model_before_any_remote_call(self):
  with patch.object(app,'remote') as remote:
   with self.assertRaises(app.Problem):app.generate(self.base(platforms=['naver'],prompt='카페 후기',campaign_min_chars=2000,campaign_max_chars=1000))
   remote.assert_not_called()


class AdditionalSafetyTests(unittest.TestCase):
 def test_large_korean_units_are_not_misread_as_five_thousand(self):
  rows=extract('본문 1만2천자 이상')['suggestions'];self.assertTrue(rows);self.assertTrue(all(row['kind']=='manual' for row in rows))
 def test_long_list_explicitly_reports_partial_extraction(self):
  self.assertTrue(extract('\n'.join('필수 문구: 문구'+str(i) for i in range(75)))['truncated'])
 def test_forbidden_ad_word_does_not_remove_received_benefit_notice(self):
  issues=preflight({'campaign_enabled':True,'disclosure':'paid','campaign_forbidden':'광고'});self.assertTrue(any(x['code']=='campaign_disclosure_forbidden' for x in issues))
 def test_manual_check_survives_unchanged_save(self):
  with tempfile.TemporaryDirectory() as folder,patch.object(app,'DATA',Path(folder)):
   with app.db() as db:db.execute('CREATE TABLE drafts(id TEXT PRIMARY KEY,title TEXT,data TEXT,updated REAL)')
   first=app.save_draft({'title':'카페','blog':'직접 확인한 글','campaign_enabled':True,'disclosure':'experience','campaign_brief':'  지도 첨부  ','campaign_manual_checks':[{'id':'b'*20,'text':'지도 확인','quote':'지도 첨부'}]})
   fp=report(first)['fingerprint'];first['campaign_manual_state']={'naver':{'b'*20:fp}};second=app.save_draft(first);self.assertTrue(report(second)['manual'][0]['checked'])

class CampaignDraftSafetyTests(unittest.TestCase):
 def test_unfinished_conflicting_conditions_can_be_saved_but_not_transferred(self):
  from extension_bridge import ExtensionBridge,HandoffError
  from naver_guard import NaverGuard
  with tempfile.TemporaryDirectory() as folder,patch.object(app,'DATA',Path(folder)):
   root=Path(folder)
   with app.db() as db:db.execute('CREATE TABLE drafts(id TEXT PRIMARY KEY,title TEXT,data TEXT,updated REAL)')
   saved=app.save_draft({'campaign_enabled':True,'campaign_min_chars':2000,'campaign_max_chars':1000,'title':'카페','blog':'작성 중 원고','disclosure':'experience'})
   self.assertEqual(app.get_draft(saved['id'])['campaign_min_chars'],2000)
   with self.assertRaises(HandoffError):ExtensionBridge(root,NaverGuard(root/'guard.json')).create(saved)
 def test_personal_mode_does_not_inherit_paused_blog_conflicts(self):
  context=writing_context({'campaign_enabled':False,'campaign_min_chars':2000,'campaign_max_chars':1000,'campaign_forbidden':'커피'});self.assertEqual(context['campaign_min_chars'],0);self.assertEqual(context['campaign_forbidden'],'')
 def test_instagram_only_ignores_blog_conflict_without_dropping_brand(self):
  import json,os
  response={'output':[{'type':'message','content':[{'type':'output_text','text':json.dumps({'instagram':'커피 한 잔의 기록'},ensure_ascii=False)}]}]}
  with patch.dict(os.environ,{'OPENAI_API_KEY':'mock'}),patch.object(app,'remote',return_value=response) as remote:
   result=app.generate({'platforms':['instagram'],'campaign_enabled':True,'campaign_brand':'메모카페','campaign_min_chars':2000,'campaign_max_chars':1000,'prompt':'커피가 고소했어','tone':'담백하고 차분하게','images':[]})
  self.assertIn('instagram',result);context=json.loads(remote.call_args.args[1]['input'][0]['content'][0]['text']);self.assertEqual(context['campaign_brand'],'메모카페');self.assertNotIn('campaign_min_chars',context)

class CampaignHttpTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  import threading
  cls.server=app.ThreadingHTTPServer(('127.0.0.1',0),app.Handler);cls.host='127.0.0.1:'+str(cls.server.server_address[1]);app.HOSTS.add(cls.host);cls.thread=threading.Thread(target=cls.server.serve_forever,daemon=True);cls.thread.start()
 @classmethod
 def tearDownClass(cls):cls.server.shutdown();cls.server.server_close();cls.thread.join();app.HOSTS.discard(cls.host)
 def post(self,path,body):
  import urllib.request,urllib.error,json
  request=urllib.request.Request('http://'+self.host+path,data=json.dumps(body).encode(),headers={'Content-Type':'application/json','X-Studio-Token':app.TOKEN})
  try:
   with urllib.request.urlopen(request,timeout=3) as response:return response.status,json.load(response)
  except urllib.error.HTTPError as error:return error.code,json.load(error)
 def test_parse_uses_neither_job_nor_remote_api(self):
  with patch.object(app,'remote') as remote,patch.object(app,'start_job') as job:
   code,result=self.post('/api/campaign/parse',{'brief':'본문 2,000자 이상'});self.assertEqual(code,200);self.assertEqual(result['suggestions'][0]['value'],2000);remote.assert_not_called();job.assert_not_called()
 def test_generation_and_revision_reject_conflict_before_allocating_job(self):
  with patch.object(app,'remote') as remote,patch.object(app,'start_job') as job:
   for path in ('/api/generate','/api/blog/expand'):
    code,result=self.post(path,{'platforms':['naver'],'campaign_enabled':True,'campaign_min_chars':2000,'campaign_max_chars':1000});self.assertEqual(code,400);self.assertEqual(result['code'],'campaign_conflict')
   remote.assert_not_called();job.assert_not_called()
