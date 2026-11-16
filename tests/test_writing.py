import unittest
import os
from writing_quality import disclose,review

class WritingChecks(unittest.TestCase):
    def test_disclosure_does_not_duplicate_and_can_be_changed(self):
        text=disclose("본문","paid")
        self.assertEqual(disclose(text,"paid"),text)
        changed=disclose(text,"gifted")
        self.assertNotIn("광고비",changed)
        self.assertEqual(disclose(changed,"none"),"본문")
    def test_unprovided_price_flagged(self):
        checks=review({"title":"카페","blog":"라떼는 6,000원이에요.","instagram":"캡션","facts":"레몬 케이크를 주문","images":["one"]})
        self.assertTrue(any("가격" in x["message"] for x in checks if x["level"]=="warning"))
    def test_given_price_not_flagged(self):
        checks=review({"title":"카페","blog":"라떼는 6,000원이에요.","instagram":"캡션","facts":"라떼 6,000원","images":["one"]})
        self.assertFalse(any("가격" in x["message"] for x in checks if x["level"]=="warning"))
    def test_placeholder_and_empty_fields_flagged(self):
        checks=review({"title":"","blog":"[주소 확인]","instagram":"","facts":"","images":[]})
        self.assertTrue(any(x["level"]=="error" for x in checks))
        self.assertTrue(any("미완성" in x["message"] for x in checks))


class MobileLineTests(unittest.TestCase):
    def test_long_lines_wrap_without_changing_words_or_photo_positions(self):
        from writing_style import mobile_lines
        value="밤에 즐긴 온천이 정말 좋았어요. 객실에서 본 바다까지 기억에 남는 부산 여행이었어요 🤍\n\n[[photo:1]]\n\n## ♨️ 밤에 즐기는 온천"
        result=mobile_lines(value)
        self.assertEqual(result.split(),value.split())
        self.assertIn("\n\n[[photo:1]]\n\n## ♨️",result)
        self.assertTrue(all(len(line)<=28 for line in result.splitlines() if not line.startswith("##")))
    def test_non_reference_layout_is_unchanged(self):
        from writing_style import mobile_lines
        value="정보 중심 글은 입력한 줄과 여백을 그대로 유지해요. 임의로 줄바꿈하지 않아요."
        self.assertEqual(mobile_lines(value,"clean"),value)
    def test_generator_uses_lively_guidance_and_real_line_formatting(self):
        import json
        from unittest.mock import patch
        import app
        content="온천이 정말 좋았어요. 객실에서 본 오션뷰와 바이레도 욕실용품도 기억에 남아요 ♨️"
        answer={"title":"온천과 오션뷰","blog":content,"instagram":"따뜻한 시간 ♨️","sources":[]}
        response={"output":[{"type":"message","content":[{"type":"output_text","text":json.dumps(answer,ensure_ascii=False)}]}]}
        with patch.dict(os.environ,{"OPENAI_API_KEY":"test-key"}),patch.object(app,"remote",return_value=response) as remote:
            result=app.generate({"prompt":"온천 너무 좋았어","facts":"바이레도 욕실용품","images":[],"tone":"밝고 경쾌한 인스타 감성으로"})
        self.assertIn("\n",result["blog"])
        self.assertIn("♨️",result["blog"])
        request=remote.call_args_list[0].args[1]
        self.assertIn("사진 분석 보고서가 아니라",request["instructions"])
        self.assertEqual(remote.call_count,2)
        self.assertTrue(all(item["type"]=="input_text" for item in remote.call_args.args[1]["input"][0]["content"]))
        self.assertIn("6~12개",request["input"][0]["content"][0]["text"])

    def test_numbered_photo_memo_is_bound_to_the_correct_image(self):
        from writing_style import photo_notes
        prompt="호텔 다녀왔어 1번사진은 온천 야경이고 2번은 온천에서 본 호텔이고 3번은 남편이야 4번은 객실 셀카야"
        notes=photo_notes(prompt,4)
        self.assertIn("온천 야경",notes[0]);self.assertIn("호텔",notes[1])
        self.assertIn("남편",notes[2]);self.assertIn("셀카",notes[3])
        self.assertNotIn("셀카",notes[2])
        self.assertEqual(photo_notes("일상 사진을 글로 써줘",2),["",""])

    def test_failed_style_pass_preserves_first_draft_and_reports_reason(self):
        import json
        from unittest.mock import patch
        import app
        def response(body):return {"output":[{"type":"message","content":[{"type":"output_text","text":json.dumps(body)}]}]}
        initial={"title":"원래 제목","blog":"보존할 본문","instagram":"캡션","sources":[]}
        malformed={"title":"제목","blog":"잘못된 사진 [[photo:99]]"}
        with patch.dict(os.environ,{"OPENAI_API_KEY":"test-key"}),patch.object(app,"remote",side_effect=[response(initial),response(malformed)]):
            result=app.generate({"prompt":"온천 이야기","images":[],"tone":"밝고 자연스러운 일상 후기체"})
        self.assertEqual(result["blog"],"보존할 본문")
        self.assertFalse(result["generation"]["style_pass"])
        self.assertTrue(any("사진 순서" in item["message"] for item in result["checks"]))
