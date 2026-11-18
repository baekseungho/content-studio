import json,os,unittest
from unittest.mock import patch
import app
from length_control import budget,violation

def response(value):return {"output":[{"type":"message","content":[{"type":"output_text","text":json.dumps(value,ensure_ascii=False)}]}],"usage":{"input_tokens":10,"output_tokens":20}}
class LengthControlTests(unittest.TestCase):
 def request(self,**extra):return {"platforms":["naver"],"prompt":"메모에 적은 맛과 메뉴만 사용해서 써줘","tone":"담백하고 차분하게","campaign_enabled":True,"campaign_min_chars":100,"images":[],**extra}
 def test_budget_scales_with_requested_blog_length_only(self):
  self.assertGreater(budget(["naver"],self.request(campaign_min_chars=2000)),budget(["naver"]))
  self.assertEqual(budget(["threads"],self.request(campaign_min_chars=2000)),budget(["threads"]))
 def test_short_draft_gets_exactly_one_repair_without_images(self):
  expanded='실제 메모에 있는 첫 설명을 조금 더 풀어 적었어요. 창가 자리에서 천천히 쉬었던 과정도 주어진 메모 안에서 정리했어요. 사용자가 적어준 구체적인 관찰과 선택 이유를 서로 다른 문장으로 이어 썼어요.'
  with patch.dict(os.environ,{"OPENAI_API_KEY":"test"}),patch.object(app,"remote",side_effect=[response({"title":"제목","blog":"짧은 초안"}),response({"blog":expanded})]) as remote:
   result=app.generate(self.request(campaign_min_chars=60))
  self.assertEqual(remote.call_count,2);self.assertTrue(result['length_status'][0]['satisfied']);self.assertTrue(result['length_status'][0]['attempted'])
  self.assertTrue(all(part['type']=='input_text' for part in remote.call_args.args[1]['input'][0]['content']))
  self.assertEqual(result['generation']['input_tokens'],20)
 def test_unfulfilled_repair_is_partial_and_does_not_loop(self):
  with patch.dict(os.environ,{"OPENAI_API_KEY":"test"}),patch.object(app,"remote",side_effect=[response({"title":"제목","blog":"첫 초안"}),response({"blog":"조금 더 긴 초안"})]) as remote:
   result=app.generate(self.request())
  self.assertEqual(remote.call_count,2);self.assertTrue(result['needs_more_notes']);self.assertFalse(result['length_status'][0]['satisfied']);self.assertIn('실제 경험',result['length_status'][0]['reason'])
 def test_style_pass_must_not_shrink_compliant_blog(self):
  original='메모에 나온 실제 경험을 자연스럽게 풀어서 작성한 원래 본문입니다.'
  with patch.dict(os.environ,{"OPENAI_API_KEY":"test"}),patch.object(app,"remote",side_effect=[response({"title":"제목","blog":original}),response({"title":"제목","blog":"너무 짧음"})]) as remote:
   result=app.generate(self.request(campaign_min_chars=20,tone='밝고 자연스러운 일상 후기체'))
  self.assertEqual(remote.call_count,2);self.assertEqual(result['blog'].split(),original.split());self.assertFalse(result['needs_more_notes'])
 def test_manual_repair_uses_current_blog_once_and_keeps_title(self):
  from platform_writing import generate_selected
  with patch.dict(os.environ,{"OPENAI_API_KEY":"test"}),patch.object(app,"remote",return_value=response({'blog':'현재 원고의 사실과 설명을 유지하면서 조금 더 자세하게 풀어 쓴 문장이에요.'})) as remote:
   result=generate_selected(self.request(campaign_min_chars=20,seed={'title':'보존할 제목','body':'현재 원고'}),lambda *args:None,app,revision=True)
  self.assertEqual(remote.call_count,1);self.assertEqual(result['title'],'보존할 제목');self.assertNotIn('instagram',result);self.assertFalse(result['needs_more_notes'])
 def test_overlong_blog_can_be_shortened(self):
  with patch.dict(os.environ,{"OPENAI_API_KEY":"test"}),patch.object(app,"remote",side_effect=[response({'title':'제목','blog':'원고가 아주 길게 작성되어 최대 글자 수를 넘긴 상황의 본문이에요.'}),response({'blog':'핵심만 남긴 글'})]):
   result=app.generate(self.request(campaign_min_chars=0,campaign_max_chars=15))
  self.assertFalse(result['needs_more_notes']);self.assertIn('핵심',result['blog'])
 def test_invalid_repair_preserves_initial_draft(self):
  with patch.dict(os.environ,{"OPENAI_API_KEY":"test"}),patch.object(app,"remote",side_effect=[response({'title':'제목','blog':'보존할 원고'}),response({'blog':'사진이 바뀐 원고 [[photo:9]]'})]):
   result=app.generate(self.request())
  self.assertIn('보존할',result['blog']);self.assertNotIn('photo:9',result['blog']);self.assertTrue(result['needs_more_notes'])

 def test_repetitive_padding_is_rejected(self):
  repeated='주어진 내용 없이 비슷한 말만 길게 반복해서는 안 되는 문장입니다. '
  with patch.dict(os.environ,{"OPENAI_API_KEY":"test"}),patch.object(app,"remote",side_effect=[response({'title':'제목','blog':'보존할 초안'}),response({'blog':repeated*5})]):
   result=app.generate(self.request())
  self.assertIn('보존할',result['blog']);self.assertTrue(result['needs_more_notes'])

 def test_expansion_target_respects_maximum_when_bounds_are_close(self):
  from length_control import planned_target
  self.assertEqual(planned_target(self.request(campaign_min_chars=2000,campaign_max_chars=2050)),2050)
  self.assertGreater(planned_target(self.request(campaign_min_chars=2000)),2000)

 def test_length_conditions_over_5000_fail_before_any_model_call(self):
  from campaigns import read_fields
  for field in ('campaign_min_chars','campaign_max_chars'):
   self.assertEqual(read_fields({field:5000})[field],5000)
   for invalid in (5001,1000000,-1,1.5):
    with self.subTest(field=field,value=invalid),patch.dict(os.environ,{'OPENAI_API_KEY':'test'}),patch.object(app,'remote') as remote:
     with self.assertRaisesRegex(app.Problem,'5,000'):app.generate(self.request(**{field:invalid}))
     remote.assert_not_called()

 def test_default_cap_repairs_ordinary_blog_without_touching_other_channels(self):
  with patch.dict(os.environ,{'OPENAI_API_KEY':'test'}),patch.object(app,'remote',side_effect=[response({'title':'제목','blog':'가'*5100}),response({'blog':'실제 내용만 유지해 간결하게 줄인 본문이에요.'})]) as remote:
   result=app.generate(self.request(campaign_enabled=False,campaign_min_chars=0))
  self.assertEqual(remote.call_count,2);self.assertEqual(result['length_status'][0]['maximum'],5000)
  self.assertFalse(result['needs_length_revision']);self.assertNotIn('instagram',result)
  self.assertIn('maximum=5000',remote.call_args_list[0].args[1]['instructions'])

 def test_default_cap_remains_actionable_when_one_repair_fails(self):
  with patch.dict(os.environ,{'OPENAI_API_KEY':'test'}),patch.object(app,'remote',side_effect=[response({'title':'제목','blog':'가'*5100}),response({'blog':'가'*5100})]) as remote:
   result=app.generate(self.request(campaign_enabled=False,campaign_min_chars=0))
  self.assertEqual(remote.call_count,2);self.assertTrue(result['needs_length_revision']);self.assertFalse(result['needs_more_notes'])
  issue=next(item for item in result['checks'] if item.get('code')=='blog_length_limit')
  self.assertEqual(issue['target'],'body');self.assertIn('5,000',issue['message'])
  self.assertEqual(result['length_status'][0]['count'],5100)

 def test_budget_cannot_grow_past_5000_even_with_unvalidated_parameters(self):
  self.assertEqual(budget(['naver'],self.request(campaign_min_chars=1000000)),budget(['naver'],self.request(campaign_min_chars=5000)))
  self.assertLessEqual(budget(['naver','tistory','instagram','threads'],self.request(campaign_min_chars=5000)),24000)
  self.assertLess(budget(['naver'],self.request(campaign_max_chars=100)),budget(['naver']))

 def test_unset_minimum_does_not_turn_5000_cap_into_a_length_target(self):
  from length_control import length_instruction,planned_target
  self.assertIn('ceiling, never a target',length_instruction({}))
  self.assertEqual(planned_target(self.request(campaign_min_chars=5000)),5000)
  self.assertEqual(violation('가'*5000,{}),0);self.assertEqual(violation('가'*5001,{}),1)
