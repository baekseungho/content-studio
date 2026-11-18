import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import app
import platform_writing as pw
from extension_bridge import ExtensionBridge
from naver_guard import NaverGuard


def response(answer,searched=False):
    return {"output":([{"type":"web_search_call","action":{"sources":[]}}] if searched else [])+[{"type":"message","content":[{"type":"output_text","text":json.dumps(answer,ensure_ascii=False)}]}],"usage":{"input_tokens":10,"output_tokens":20}}

class PlatformGenerationTests(unittest.TestCase):
    def request(self,platforms,**extra):return {"platforms":platforms,"prompt":"창가에서 커피 마시며 쉬었어","images":[],"tone":"담백하고 차분하게",**extra}

    def test_instagram_only_requests_and_returns_only_its_fields(self):
        answer={"instagram":"창가에서 잠깐 쉬었어요.","title":"만들면 안 되는 제목","blog":"보내면 안 되는 본문","threads":"미선택 글"}
        with patch.dict(os.environ,{"OPENAI_API_KEY":"test"}),patch.object(app,"remote",return_value=response(answer)) as remote:
            result=app.generate(self.request(["instagram"],blog="기존 긴 원고",threads="유지할 스레드"))
        self.assertEqual(remote.call_count,1);self.assertIn("instagram",result)
        self.assertTrue(all(key not in result for key in ("blog","title","threads","tistory")))
        payload=remote.call_args.args[1];context=json.loads(payload["input"][0]["content"][0]["text"])
        self.assertEqual(context["requested_platforms"],["instagram"])
        self.assertNotIn("기존 긴 원고",json.dumps(payload,ensure_ascii=False));self.assertNotIn("유지할 스레드",json.dumps(payload,ensure_ascii=False))
        self.assertLess(payload["max_output_tokens"],3000)

    def test_threads_only_polish_does_not_require_a_blog(self):
        answer={"threads":"창가 자리, 오늘 잘 골랐어."}
        with patch.dict(os.environ,{"OPENAI_API_KEY":"test"}),patch.object(app,"remote",return_value=response(answer)) as remote:
            result=app.generate(self.request(["threads"],tone="밝고 자연스러운 일상 후기체"))
        self.assertEqual(remote.call_count,2);self.assertTrue(result["generation"]["style_pass"])
        context=json.loads(remote.call_args.args[1]["input"][0]["content"][0]["text"])
        self.assertEqual(list(context["draft"]),["threads"])
        self.assertTrue(all(item["type"]=="input_text" for item in remote.call_args.args[1]["input"][0]["content"]))
        self.assertNotIn("title",result);self.assertEqual(result["generation"]["input_tokens"],20)

    def test_tistory_and_naver_are_independent_outputs(self):
        answer={"title":"네이버 제목","blog":"네이버 기록","tistory_title":"티스토리 제목","tistory":"티스토리 기록"}
        with patch.dict(os.environ,{"OPENAI_API_KEY":"test"}),patch.object(app,"remote",return_value=response(answer)):
            result=app.generate(self.request(["naver","tistory"]))
        self.assertIn("네이버 기록",result["blog"]);self.assertIn("티스토리 기록",result["tistory"])
        self.assertNotIn("instagram",result);self.assertNotIn("threads",result)

    def test_missing_selected_output_fails_and_no_unselected_output_is_needed(self):
        with patch.dict(os.environ,{"OPENAI_API_KEY":"test"}),patch.object(app,"remote",return_value=response({"instagram":"다른 플랫폼"})):
            with self.assertRaises(app.Problem):app.generate(self.request(["naver"]))
        for bad in ([],"naver",["unknown"],["threads","threads"],[False]):
            with self.subTest(bad=bad),self.assertRaises(app.Problem):app.generate(self.request(bad))

    def test_english_instagram_translates_required_notes_without_blog(self):
        answer={"instagram":"A little window-seat break.","facts_translation":"The coffee was hot."}
        with patch.dict(os.environ,{"OPENAI_API_KEY":"test"}),patch.object(app,"remote",return_value=response(answer)):
            result=app.generate(self.request(["instagram"],language="en",facts="커피가 뜨거웠어요."))
        self.assertIn("The coffee was hot.",result["instagram"]);self.assertNotIn("blog",result)
        self.assertEqual(result["facts_translation_source"],"커피가 뜨거웠어요.")

    def test_english_threads_does_not_generate_unused_translation(self):
        with patch.dict(os.environ,{"OPENAI_API_KEY":"test"}),patch.object(app,"remote",return_value=response({"threads":"A good window seat today."})):
            result=app.generate(self.request(["threads"],language="en",facts="창가에 앉았어요."))
        self.assertNotIn("facts_translation",result)

    def test_bad_polish_retains_selected_original_and_reports_usage(self):
        with patch.dict(os.environ,{"OPENAI_API_KEY":"test"}),patch.object(app,"remote",side_effect=[response({"threads":"원래 글이야."}),response({"blog":"엉뚱한 응답"})]):
            result=app.generate(self.request(["threads"],tone="밝고 자연스러운 일상 후기체"))
        self.assertEqual(result["threads"],"원래 글이야.");self.assertFalse(result["generation"]["style_pass"])
        self.assertEqual(result["generation"]["output_tokens"],40)
        self.assertTrue(any("다듬기" in item["message"] for item in result["checks"]))

    def test_research_reuses_only_identical_server_observed_context(self):
        pw._CACHE.clear()
        place={"name":"샘플카페","address":"서울 성동구 성수일로 12-3"}
        researched={"facts":[],"sources":[],"usage":{"input_tokens":4},"web_search_calls":1,"notice":"확인된 상세정보 없음"}
        with patch.dict(os.environ,{"OPENAI_API_KEY":"test"}),patch("platform_writing.research_place",return_value=researched) as research,patch.object(app,"remote",return_value=response({"instagram":"잠깐 쉬었어요.","threads":"잠깐 쉬었어."})):
            first=app.generate(self.request(["instagram"],selected_place=place,research=True))
            additional=app.generate(self.request(["threads"],selected_place=place,research=True,reuse_research=True))
            changed=app.generate(self.request(["threads"],selected_place=place,research=True,reuse_research=True,facts="다른 메모"))
        self.assertEqual(research.call_count,2);self.assertFalse(first["generation"]["reused_place_research"])
        self.assertTrue(additional["generation"]["reused_place_research"]);self.assertEqual(additional["generation"]["web_search_calls"],0)
        self.assertFalse(changed["generation"]["reused_place_research"])

    def test_partial_save_does_not_create_unselected_disclosure_or_photo_placeholders(self):
        with tempfile.TemporaryDirectory() as directory,patch.object(app,"DATA",Path(directory)):
            with app.db() as db:db.execute("CREATE TABLE drafts(id TEXT PRIMARY KEY,title TEXT,data TEXT,updated REAL)")
            saved=app.save_draft({"selective_generation":True,"editing_platform":"instagram","instagram":"새 인스타 글","blog":"보존할 네이버 글","tistory":"보존할 티스토리 글","threads":"보존할 스레드","disclosure":"paid","platform_languages":{"naver":"ko","instagram":"en"},"language":"en"})
            exact=app.save_draft({**saved,"editing_platform":"threads","blog":"[내가 쓴 링크](https://example.com)"})
            self.assertEqual(exact["blog"],"[내가 쓴 링크](https://example.com)")
            self.assertEqual(saved["blog"],"보존할 네이버 글");self.assertEqual(saved["tistory"],"보존할 티스토리 글");self.assertEqual(saved["threads"],"보존할 스레드")
            self.assertTrue(saved["instagram"].startswith("Paid partnership."))
            empty=app.save_draft({"selective_generation":True,"editing_platform":"threads","threads":"스레드 글","disclosure":"gifted"})
            self.assertEqual(empty["blog"],"");self.assertEqual(empty["tistory"],"");self.assertEqual(empty["instagram"],"")
            legacy=app.save_draft({"title":"옛 제목","blog":"기존 공통 원고"})
            self.assertEqual(app.get_draft(legacy["id"])["tistory"],legacy["blog"])

    def test_language_is_projected_per_platform_for_publishing_and_export(self):
        draft={"id":"a"*32,"language":"en","platform_languages":{"naver":"ko","instagram":"en"},"title":"한국어 제목","blog":"한국어 원고","instagram":"English caption.","facts":"바뀐 필수 메모","facts_translation":"Old note.","facts_translation_source":"예전 필수 메모","images":["sample"]}
        self.assertIn('lang="ko"',app.blog_html(pw.view({**draft,"images":[]},"naver")))
        checks=app.review({**pw.view(draft,"instagram"),"review_channel":"instagram"})
        self.assertTrue(any(item["level"]=="error" and "영어" in item["message"] for item in checks))
        draft["language"]="ko"
        with patch.object(app,"get_draft",return_value=draft),patch.object(app,"instagram_configuration",return_value={"ready":True}),patch.object(app,"media_base_url",return_value="https://example.com"):
            with self.assertRaisesRegex(app.Problem,"영어 필수 메모"):app.publish_instagram(draft["id"])

    def test_tistory_handoff_receives_only_tistory_body_and_title(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);bridge=ExtensionBridge(root,NaverGuard(root/'guard.json'),channel="tistory")
            draft={"id":"a"*32,"title":"네이버","blog":"네이버 원고","tistory_title":"Tistory title","tistory":"Independent Tistory draft.","images":[],"platform_languages":{"tistory":"en"}}
            result=bridge.redeem(bridge.create(draft)["code"])
            self.assertIn("Independent Tistory draft.",json.dumps(result,ensure_ascii=False));self.assertNotIn("네이버 원고",json.dumps(result,ensure_ascii=False))

if __name__=="__main__":unittest.main()
