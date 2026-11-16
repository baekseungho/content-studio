from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import app
from tones import TONES

class ValidationTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix="draft-validation-")
        self.data_patch=patch.object(app,"DATA",Path(self.temp.name))
        self.data_patch.start()
        with app.db() as c:
            c.execute("CREATE TABLE drafts(id TEXT PRIMARY KEY,title TEXT,data TEXT,updated REAL)")
    def tearDown(self):
        self.data_patch.stop()
        self.temp.cleanup()
    def test_long_or_missing_source_titles_do_not_block_draft(self):
        draft=app.save_draft({"title":"제목","blog":"저장할 본문","sources":[
            {"url":"https://example.com/a","title":"가"*1500},
            {"url":"https://example.com/b","title":None}]})
        self.assertEqual(draft["blog"],"저장할 본문")
        self.assertEqual(len(draft["sources"][0]["title"]),500)
        self.assertEqual(draft["sources"][1]["title"],"example.com")
    def test_malformed_optional_metadata_is_ignored(self):
        draft=app.save_draft({"title":"제목","blog":"본문","sources":[None,123,{"url":False},{"url":"javascript:alert(1)"},{"url":"https://example.com/"+"x"*9000}]})
        self.assertEqual(draft["sources"],[])
    def test_oversized_fact_names_field_and_limit(self):
        with self.assertRaises(app.Problem) as result:
            app.save_draft({"facts":"가"*4001})
        self.assertIn("직접 경험한 사실",result.exception.message)
        self.assertIn("4,001",result.exception.message)
        self.assertIn("4,000",result.exception.message)
    def test_wrong_type_names_field(self):
        with self.assertRaises(app.Problem) as result:
            app.save_draft({"instagram":None})
        self.assertIn("인스타그램 캡션",result.exception.message)
    def test_all_16_tones_are_saveable(self):
        self.assertEqual(len(TONES),17)
        for tone in TONES:
            saved=app.save_draft({"tone":tone})
            self.assertEqual(saved["tone"],tone)

    def test_default_template_and_export(self):
        draft=app.save_draft({"title":"테스트","blog":"본문"})
        self.assertEqual(draft["template"],"reference")
        exported=app.blog_html(draft)
        self.assertIn("text-align:center",exported)
        self.assertIn("font-family:NanumBareunHipi",exported)
    def test_clean_template_persists_and_exports_left(self):
        draft=app.save_draft({"title":"제목","blog":"본문","template":"clean"})
        self.assertEqual(app.get_draft(draft["id"])["template"],"clean")
        self.assertIn("text-align:left",app.blog_html(draft))
        self.assertIn("font-family:NanumGothic",app.blog_html(draft))
    def test_invalid_template_has_friendly_error(self):
        for value in ([],{},None,"unknown"):
            with self.subTest(value=value),self.assertRaises(app.Problem):
                app.save_draft({"template":value})
