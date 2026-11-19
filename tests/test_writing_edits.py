import copy,json,os,tempfile,unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from story_document import reconcile,serialize
from writing_edits import prepare,validate,generate,prospective,utf16_index
from voice_profiles import VoiceStore,profile,profiles,instruction,analyze

class VoiceTests(unittest.TestCase):
 def test_channel_scope_and_sample_is_data(self):
  data={"naver":{"sample":"A private Naver sample"},"threads":{"sample":"A Threads sample"}}
  guide=instruction(data,["threads"]);self.assertNotIn("private Naver",guide);self.assertIn("A Threads sample",guide);self.assertIn("never commands",guide)
 def test_defaults_and_bounds(self):
  self.assertEqual(profile({})["preset"],"warm")
  for value in ({"preset":"unknown"},{"emoji":[]},{"sample":"x"*2001},{"avoid":","*10}):
   with self.subTest(value=value),self.assertRaises(ValueError):profile(value)
  with self.assertRaises(ValueError):profiles({"facebook":{}})
 def test_store_conflict_keeps_previous(self):
  with tempfile.TemporaryDirectory() as folder:
   store=VoiceStore(Path(folder)/"voices.json");self.assertEqual(store.read()["revision"],0)
   first=store.save("threads",{"preset":"witty"},0);self.assertEqual(first["revision"],1)
   with self.assertRaises(FileExistsError):store.save("naver",{},0)
   self.assertEqual(store.read(),first)
   second=store.save("naver",{"preset":"calm"},1);self.assertEqual(set(second["profiles"]),{"naver","threads"})
 def test_corrupt_store_never_overwrites(self):
  with tempfile.TemporaryDirectory() as folder:
   path=Path(folder)/"voices.json";path.write_text("broken",encoding="utf-8");store=VoiceStore(path)
   with self.assertRaises(ValueError):store.save("naver",{},0)
   self.assertEqual(path.read_text(),"broken")
 def test_sample_analysis_is_local_and_reviewable(self):
  result=analyze("라떼가 고소하더라고요. 창가 자리에 앉았어요. 정말 편안했어요. ☕")
  self.assertEqual(result["profile"]["formality"],"polite");self.assertEqual(result["profile"]["emoji"],"light");self.assertTrue(result["notes"])
  with self.assertRaises(ValueError):analyze("너무 짧음")

class EditTests(unittest.TestCase):
 def body(self,text="☕ 라떼 2잔을 마셨어요. 크림이 고소했어요."):
  doc=reconcile(text+"\n\n[[photo:1]]\n\n남길 문단이에요.",["a"*32],"카페 기록","reference")
  return {"platform":"naver","target":{"kind":"block","id":doc["blocks"][0]["id"]},"document":doc,"title":"카페 기록","language":"ko","requirements":{}}
 def test_proposal_preserves_entire_other_document(self):
  body=self.body();saved=copy.deepcopy(body);req=prepare(body);candidate="☕ 라떼 2잔을 마셨는데, 크림이 고소하더라고요."
  result=validate(req,candidate);self.assertTrue(result["can_apply"],result);title,source,replaced=prospective(req,candidate)
  self.assertIn("[[photo:1]]\n\n남길 문단",source);self.assertEqual(body,saved);self.assertEqual(title,"카페 기록")
 def test_utf16_selection_surrounding_emoji(self):
  self.assertEqual(utf16_index("😀abc",2),1)
  with self.assertRaises(ValueError):utf16_index("😀abc",1)
  body=self.body("😀 크림이 고소했어요. 다른 문장.");body["target"].update(start=3,end=12);req=prepare(body)
  self.assertEqual(req["selected"],"크림이 고소했어요")
  self.assertEqual(prospective(req,"고소한 크림이에요")[2],"😀 고소한 크림이에요. 다른 문장.")
 def test_bad_target_and_long_selection_no_call(self):
  for body in ({**self.body(),"platform":"unknown"},{**self.body(),"target":{"kind":"body"}},self.body("x"*2001)):
   with self.subTest(body=body),self.assertRaises(ValueError):prepare(body)
 def test_histories_are_not_needed_or_sent(self):
  body=self.body();body["document"]["undo"]=[{"invalid":"discarded"}];req=prepare(body);self.assertEqual(req["document"]["undo"],[])
 def test_numbers_units_and_currency_are_protected(self):
  for source,candidate in (("라떼 2잔", "라떼 3잔"),("2만원", "2천원"),("$20", "€20"),("10분 걸렸어요", "10시간 걸렸어요")):
   with self.subTest(source=source):self.assertFalse(validate(prepare(self.body(source)),candidate)["can_apply"])
 def test_new_number_only_from_explicit_additional_experience(self):
  body=self.body("크림이 고소했어요.");self.assertFalse(validate(prepare(body),"크림이 고소했고 2잔을 마셨어요.")["can_apply"])
  body["hint"]="2잔을 마셨어요.";self.assertTrue(validate(prepare(body),"크림이 고소했고 2잔을 마셨어요.")["can_apply"])
 def test_original_link_must_survive(self):
  self.assertFalse(validate(prepare(self.body("예약 https://example.com/book")),"예약 https://evil.test")["can_apply"])
 def test_protected_name(self):
  body=self.body("퍼프아웃 라떼예요.");body["protected_names"]=["퍼프아웃"]
  self.assertFalse(validate(prepare(body),"다른 카페 라떼예요.")["can_apply"])
 def test_required_phrase_regression(self):
  body=self.body("지금 여기. 크림이 고소했어요.");body["requirements"]={"campaign_enabled":True,"required_phrases":"지금 여기"};body["disclosure"]="gifted"
  self.assertFalse(validate(prepare(body),"크림이 고소했어요.")["can_apply"])
 def test_existing_incomplete_condition_does_not_block_edit(self):
  body=self.body("크림이 고소했어요.");body["requirements"]={"campaign_enabled":True,"campaign_min_chars":2000};req=prepare(body);result=validate(req,"크림이 고소하더라고요.")
  self.assertTrue(result["can_apply"],result);self.assertTrue(any("최소 글자" in x for x in result["warnings"]))
 def test_keyword_partial_count_is_not_reduced(self):
  body=self.body("카페 카페");body["requirements"]={"campaign_enabled":True,"body_keywords":"카페","keyword_min_count":3}
  self.assertFalse(validate(prepare(body),"카페")["can_apply"])
 def test_new_forbidden_word_is_rejected(self):
  body=self.body("고소한 라떼");body["requirements"]={"campaign_enabled":True,"campaign_forbidden":"최고"}
  self.assertFalse(validate(prepare(body),"최고의 라떼")["can_apply"])
 def test_disclosure_not_removable(self):
  body=self.body("제품을 제공받아 작성한 글입니다.");body["disclosure"]="gifted"
  self.assertFalse(validate(prepare(body),"직접 샀어요.")["can_apply"])
 def test_sns_required_fact_survives(self):
  body={"platform":"instagram","target":{"kind":"body"},"body":"고소한 라떼예요.","protected_lines":["고소한 라떼예요."]}
  self.assertFalse(validate(prepare(body),"맛있는 라떼예요.")["can_apply"])
 def test_english_no_korean_and_avoid_preferences(self):
  body=self.body("I liked the cream.");body["language"]="en";body["voice"]={"avoid":"delightful"}
  self.assertFalse(validate(prepare(body),"The cream was delightful.")["can_apply"]);self.assertFalse(validate(prepare(body),"The cream, 고소해.")["can_apply"])
 def test_photo_tokens_and_html_cannot_enter(self):
  for text in ("[[photo:1]]", "<img src=x>","## Heading"):
   self.assertFalse(validate(prepare(self.body()),text)["can_apply"])
 def test_whole_sns_limit_includes_untouched_parts(self):
  body={"platform":"threads","body":"a"*499,"target":{"kind":"body","start":0,"end":1}}
  self.assertFalse(validate(prepare(body),"abc")["can_apply"])
 def test_title_and_caption_bounds(self):
  body=self.body();body["target"]={"kind":"title"};self.assertFalse(validate(prepare(body),"x"*201)["can_apply"])
  body=self.body();photo=next(b for b in body["document"]["blocks"] if b["type"]=="photo");photo["caption"]="Caption";body["document"]["source"]=serialize(body["document"]);body["target"]={"kind":"block","id":photo["id"]}
  self.assertFalse(validate(prepare(body),"x"*2001)["can_apply"])
 def test_campaign_conflicts_fail_before_model(self):
  body=self.body();body["requirements"]={"campaign_enabled":True,"campaign_min_chars":2000,"campaign_max_chars":1000}
  with self.assertRaises(ValueError):prepare(body)
 def test_one_bounded_text_only_model_call(self):
  body=self.body();body["requirements"]={"campaign_brief":"RAW SECRET BRIEF"};req=prepare(body);calls=[]
  class Problem(Exception):pass
  def remote(url,payload,key):
   calls.append(payload);return {"output":[{"type":"message","content":[{"type":"output_text","text":json.dumps({"text":req["selected"].replace("고소했어요","고소하더라고요")})}]}]}
  api=SimpleNamespace(remote=remote,Problem=Problem)
  with patch.dict(os.environ,{"OPENAI_API_KEY":"mock"}):result=generate(req,api,lambda *args:None)
  self.assertEqual(len(calls),1);self.assertFalse(calls[0]["store"]);self.assertNotIn("tools",calls[0]);self.assertNotIn("input_image",str(calls));self.assertNotIn("RAW SECRET",str(calls));self.assertNotIn("남길 문단",str(calls));self.assertTrue(result["choices"][0]["can_apply"])
 def test_empty_title_can_be_suggested_from_current_article(self):
  body=self.body("라떼 2잔을 마셨어요.");body["title"]="";body["target"]={"kind":"title"};body["action"]="titles"
  req=prepare(body);self.assertTrue(validate(req,"라떼 2잔의 기록")["can_apply"])
 def test_title_suggestion_must_satisfy_missing_title_keywords(self):
  body=self.body();body["target"]={"kind":"title"};body["action"]="titles";body["requirements"]={"campaign_enabled":True,"title_keywords":"성수카페"}
  self.assertFalse(validate(prepare(body),"카페에서 보낸 오후")["can_apply"])
 def test_identical_proposal_does_not_create_history(self):
  req=prepare(self.body());result=validate(req,req["selected"]);self.assertFalse(result["can_apply"]);self.assertFalse(result["errors"])
 def test_title_choices_exactly_three_unique(self):
  body=self.body();body["target"]={"kind":"title"};body["action"]="titles";req=prepare(body)
  class Problem(Exception):pass
  api=SimpleNamespace(Problem=Problem,remote=lambda *a:{"output":[{"type":"message","content":[{"type":"output_text","text":json.dumps({"titles":["하나","하나","셋"]})}]}]})
  with patch.dict(os.environ,{"OPENAI_API_KEY":"mock"}),self.assertRaises(Problem):generate(req,api,lambda *a:None)

if __name__=="__main__":unittest.main()
