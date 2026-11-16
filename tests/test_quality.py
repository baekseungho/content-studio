import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from content_rules import clean_blog
from naver_guard import NaverGuard

class ContentRulesTests(unittest.TestCase):
    def test_inline_citations_and_urls_removed_but_photos_preserved(self):
        result=clean_blog("첫인상이에요.([hongsi.io](https://hongsi.io/place?utm_source=openai))\n[[photo:1]]\n[메뉴 안내](https://example.com/menu)\nhttps://example.com/extra")
        self.assertNotIn("http",result)
        self.assertNotIn("hongsi.io",result)
        self.assertIn("첫인상이에요.",result)
        self.assertIn("[[photo:1]]",result)
        self.assertIn("메뉴 안내",result)
    def test_citation_tokens_removed(self):
        self.assertEqual(clean_blog("본문citeturn0search0"),"본문")

class NaverGuardTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.guard=NaverGuard(Path(self.temp.name)/"guard.json")
    def tearDown(self):
        self.temp.cleanup()
    def test_cooldown_persists_restart(self):
        self.guard.reserve("first")
        with self.assertRaises(ValueError):
            NaverGuard(self.guard.path).reserve("second")
    def test_cooldown_exactly_sixty_seconds(self):
        with patch("naver_guard.time.time",return_value=100000):
            self.guard.reserve("first")
        with patch("naver_guard.time.time",return_value=100059.9):
            self.assertEqual(self.guard.status()["cooldown_seconds"],1)
            with self.assertRaises(ValueError):
                self.guard.reserve("second")
        with patch("naver_guard.time.time",return_value=100060):
            self.guard.reserve("second")

    def test_security_lock_requires_manual_acknowledgement(self):
        self.guard.block("보호조치")
        with self.assertRaises(ValueError):
            self.guard.reserve("first")
        self.guard.unblock()
        self.guard.reserve("first")
    def test_completed_draft_not_repeated(self):
        self.guard.complete("first")
        with self.assertRaises(ValueError):
            self.guard.reserve("first")
    def test_no_daily_limit_after_many_attempts(self):
        with patch("naver_guard.time.time",return_value=100000):
            self.guard.write({"attempts":[97000,98000,99000]*10,"completed":[],"blocked":False})
            self.guard.reserve("next")
            self.assertIsNone(self.guard.status()["limit_24h"])
            self.assertEqual(self.guard.status()["attempts_24h"],31)

    def test_explicit_repeat_allows_completed_draft_after_cooldown(self):
        self.guard.complete("first")
        with patch("naver_guard.time.time",return_value=100000):
            self.guard.reserve("first",allow_repeat=True)
        with patch("naver_guard.time.time",return_value=100059):
            with self.assertRaisesRegex(ValueError,"1秒|1초"):
                self.guard.reserve("first",allow_repeat=True)
        with patch("naver_guard.time.time",return_value=100060):
            self.guard.reserve("first",allow_repeat=True)
    def test_repeat_never_bypasses_security_block(self):
        self.guard.complete("first");self.guard.block("추가 인증")
        with self.assertRaises(ValueError):self.guard.reserve("first",allow_repeat=True)
