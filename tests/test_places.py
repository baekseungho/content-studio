import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import urllib.error
import app
from places import selected_place,search_places,research_place,identity_matches,PlaceError

PLACE={"name":"샘플카페 성수점","address":"서울특별시 성동구 성수일로 12-3","road_address":"서울특별시 성동구 성수일로 12-3"}
URL="https://example.com/seongsu"

def response(value,searched=True):
    return {"output":([{"type":"web_search_call","action":{"sources":[{"url":URL,"title":"성수점 안내"}]}}] if searched else [])+[{"type":"message","content":[{"type":"output_text","text":json.dumps(value,ensure_ascii=False)}]}],"usage":{"input_tokens":5,"output_tokens":7}}

def fact(**overrides):
    return {"scope":"general","conditions":"","kind":"parking","name":PLACE["name"],"address":PLACE["address"],"text":"주차 공간은 없다고 안내되어 있어요.","url":URL,**overrides}

class PlaceTests(unittest.TestCase):
    def test_place_is_optional_and_unsafe_link_is_removed(self):
        self.assertIsNone(selected_place(None))
        self.assertEqual(selected_place({**PLACE,"url":"javascript:alert(1)"})["url"],"")
        for invalid in ([],"카페",{}, {"name":"카페","address":""},{**PLACE,"name":"x"*151}):
            with self.assertRaises(PlaceError):selected_place(invalid)

    def test_exact_address_and_branch_are_required(self):
        place=selected_place(PLACE)
        self.assertTrue(identity_matches(place,"샘플카페 성수점 공식", "서울 성동구 성수일로 12-3 (성수동)"))
        self.assertFalse(identity_matches(place,"샘플카페 강남점",PLACE["address"]))
        self.assertFalse(identity_matches(place,PLACE["name"],"서울 성동구 성수일로 123"))
        self.assertFalse(identity_matches(place,PLACE["name"],"서울 성동구 성수일로 12-30"))
        self.assertFalse(identity_matches(place,"샘플카페",PLACE["address"]))

    def test_naver_cloud_search_uses_private_headers_and_distinct_addresses(self):
        result={"items":[{"title":"<b>샘플카페</b> 성수점","address":PLACE["address"],"roadAddress":PLACE["address"],"category":"음식점&gt;카페","link":URL}, {"title":"샘플카페 강남점","address":"서울 강남구 강남대로 100"}]}
        with patch.dict(os.environ,{"NAVER_SEARCH_CLIENT_ID":"private-id","NAVER_SEARCH_CLIENT_SECRET":"private-secret","NAVER_SEARCH_PROVIDER":"ncp"}),patch("places.urllib.request.urlopen",return_value=io.BytesIO(json.dumps(result).encode())) as opened:
            found=search_places("성수 샘플카페",None)
        self.assertEqual(len(found["places"]),2)
        self.assertEqual(found["places"][0]["name"],"샘플카페 성수점")
        request=opened.call_args.args[0]
        self.assertTrue(request.full_url.startswith("https://naverapihub.apigw.ntruss.com/search/v1/local?"))
        self.assertNotIn("private",request.full_url)
        self.assertEqual(request.get_header("X-ncp-apigw-api-key"),"private-secret")
        self.assertNotIn("private",json.dumps(found))

    def test_search_connection_error_allows_direct_entry(self):
        with patch.dict(os.environ,{"NAVER_SEARCH_CLIENT_ID":"id","NAVER_SEARCH_CLIENT_SECRET":"secret","NAVER_SEARCH_PROVIDER":"ncp"}),patch("places.urllib.request.urlopen",side_effect=urllib.error.URLError("secret")):
            with self.assertRaisesRegex(PlaceError,"직접"):search_places("성수 카페",None)

    def test_web_candidates_require_actual_source_and_address(self):
        results={"places":[{**PLACE,"url":URL},{"name":"가짜","address":"서울 성수일로 1","url":"https://invented.invalid"},{"name":"이름만","address":"서울 성수동","url":URL}]}
        with patch.dict(os.environ,{"NAVER_SEARCH_CLIENT_ID":"","NAVER_SEARCH_CLIENT_SECRET":"","OPENAI_API_KEY":"test"}):
            found=search_places("성수 샘플카페",lambda *args:response(results))
        self.assertEqual([x["name"] for x in found["places"]],[PLACE["name"]])

    def test_search_without_any_key_is_actionable(self):
        with patch.dict(os.environ,{"NAVER_SEARCH_CLIENT_ID":"","NAVER_SEARCH_CLIENT_SECRET":"","OPENAI_API_KEY":""}):
            with self.assertRaisesRegex(PlaceError,"직접"):search_places("성수 카페",None)

    def test_research_drops_other_branch_address_and_uncited_url(self):
        results={"facts":[fact(),fact(name="샘플카페 강남점"),fact(address="서울 강남구 강남대로 100"),fact(url="https://invented.invalid"),fact(kind="website")]}
        found=research_place(selected_place(PLACE),lambda *args:response(results))
        self.assertEqual(len(found["facts"]),1)
        self.assertIn("제외",found["notice"])
        self.assertEqual([x["url"] for x in found["sources"]],[URL])

    def test_member_benefits_and_missing_conditions_are_not_general_facts(self):
        url="https://example.com/front/memnotice/membership"
        result=response({"facts":[fact(url=url),fact(scope="members_only"),fact(conditions={}),fact(conditions="투숙객에 한함")]})
        result["output"][0]["action"]["sources"].append({"url":url})
        found=research_place(selected_place(PLACE),lambda *args:result)
        self.assertEqual(len(found["facts"]),1)
        self.assertIn("투숙객에 한함",found["facts"][0]["text"])
        self.assertIn("제외",found["notice"])

    def test_research_empty_or_malformed_falls_back_without_guessing(self):
        for result in (response({"facts":[]}),response([]),response({"facts":[fact()]},searched=False)):
            found=research_place(selected_place(PLACE),lambda *args:result)
            self.assertEqual(found["facts"],[])
            self.assertIn("찾지 못했어요",found["notice"])

    def test_selected_research_is_separate_and_usage_includes_it(self):
        answer={"title":"샘플카페 성수점","blog":"직접 적은 경험이에요.","instagram":"내가 적은 느낌이에요.","threads":"짧은 기록"}
        request={"prompt":"성수에서 쉬었어","tone":"밝고 자연스러운 일상 후기체","selected_place":PLACE,"research":True,"images":[]}
        with patch.dict(os.environ,{"OPENAI_API_KEY":"test"}),patch.object(app,"remote",side_effect=[response({"facts":[fact(),fact(name="샘플카페 강남점")]}),response(answer,searched=False),response(answer,searched=False)]) as remote:
            generated=app.generate(request)
        self.assertEqual(remote.call_count,3)
        for call in remote.call_args_list[1:]:
            payload=call.args[1];context=json.loads(payload["input"][0]["content"][0]["text"])
            self.assertNotIn("tools",payload)
            self.assertEqual(context["selected_place"]["name"],PLACE["name"])
            self.assertEqual(len(context["verified_place_facts"]),1)
            self.assertIn("장소 정확성 규칙",payload["instructions"])
        self.assertEqual(generated["generation"]["input_tokens"],15)
        self.assertEqual(generated["generation"]["web_search_calls"],1)
        self.assertEqual(generated["selected_place"]["name"],PLACE["name"])
        self.assertTrue(any("제외" in check["message"] for check in generated["checks"]))

    def test_no_research_does_not_lookup_even_with_selected_place(self):
        answer={"title":"제목","blog":"본문","instagram":"캡션","threads":"기록"}
        with patch.dict(os.environ,{"OPENAI_API_KEY":"test"}),patch.object(app,"remote",return_value=response(answer,False)) as remote:
            generated=app.generate({"prompt":"기록","tone":"담백하고 차분하게","selected_place":PLACE,"research":False})
        self.assertEqual(remote.call_count,1)
        payload=remote.call_args.args[1]
        self.assertNotIn("tools",payload)
        self.assertEqual(json.loads(payload["input"][0]["content"][0]["text"])["verified_place_facts"],[])
        self.assertFalse(generated["research"])

    def test_unselected_research_keeps_existing_search_workflow(self):
        answer={"title":"제목","blog":"본문","instagram":"캡션","threads":"기록"}
        with patch.dict(os.environ,{"OPENAI_API_KEY":"test"}),patch.object(app,"remote",return_value=response(answer)) as remote:
            generated=app.generate({"prompt":"기록","tone":"담백하고 차분하게","research":True})
        self.assertEqual(remote.call_count,1)
        self.assertIn("tools",remote.call_args.args[1]);self.assertIsNone(generated["selected_place"])

    def test_failed_selected_research_uses_notes_and_reports_reason(self):
        answer={"title":"제목","blog":"본문","instagram":"캡션","threads":"기록"}
        with patch.dict(os.environ,{"OPENAI_API_KEY":"test"}),patch.object(app,"remote",side_effect=[app.Problem("검색 실패",502),response(answer,False)]) as remote:
            generated=app.generate({"prompt":"기록","tone":"담백하고 차분하게","selected_place":PLACE,"research":True})
        self.assertNotIn("tools",remote.call_args.args[1])
        self.assertTrue(any("검색을 마치지 못했어요" in item["message"] for item in generated["checks"]))

    def test_place_and_research_survive_save_and_can_be_cleared(self):
        with tempfile.TemporaryDirectory() as directory,patch.object(app,"DATA",Path(directory)):
            with app.db() as c:c.execute("CREATE TABLE drafts(id TEXT PRIMARY KEY,title TEXT,data TEXT,updated REAL)")
            draft=app.save_draft({"title":"제목","blog":"본문","instagram":"캡션","selected_place":PLACE,"research":True})
            loaded=app.get_draft(draft["id"])
            self.assertEqual(loaded["selected_place"]["address"],PLACE["address"]);self.assertTrue(loaded["research"])
            cleared=app.save_draft({**loaded,"selected_place":None,"research":False})
            self.assertIsNone(cleared["selected_place"]);self.assertFalse(cleared["research"]);self.assertEqual(cleared["blog"],loaded["blog"])

if __name__=="__main__":unittest.main()
