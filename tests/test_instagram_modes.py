import os
import unittest
from unittest.mock import patch
import app

class InstagramLoginModes(unittest.TestCase):
    def test_unified_calls_meta_host(self):
        with patch.dict(os.environ,{"INSTAGRAM_LOGIN_TYPE":"unified","INSTAGRAM_ACCESS_TOKEN":"EAA-test"}),patch.object(app,"remote",return_value={"id":"123"}) as remote:
            app.graph("123?fields=id")
        self.assertTrue(remote.call_args.args[0].startswith("https://graph.facebook.com/"))

    def test_instagram_calls_instagram_host(self):
        with patch.dict(os.environ,{"INSTAGRAM_LOGIN_TYPE":"instagram","INSTAGRAM_ACCESS_TOKEN":"IGAA-test"}),patch.object(app,"remote",return_value={"id":"123"}) as remote:
            app.graph("me?fields=id")
        self.assertTrue(remote.call_args.args[0].startswith("https://graph.instagram.com/"))

    def test_unified_connection_checks_account_not_system_user(self):
        with patch.dict(os.environ,{"INSTAGRAM_LOGIN_TYPE":"unified","INSTAGRAM_ACCOUNT_ID":"123"}),patch.object(app,"graph",return_value={"id":"123"}) as graph:
            result=app.check_instagram_connection()
        graph.assert_called_once_with("123?fields=id")
        self.assertTrue(result["account_matches"])

    def test_eaa_token_is_not_rejected_by_prefix(self):
        with patch.dict(os.environ,{"INSTAGRAM_LOGIN_TYPE":"unified","INSTAGRAM_ACCOUNT_ID":"123","INSTAGRAM_ACCESS_TOKEN":"EAA-test","PUBLIC_MEDIA_BASE_URL":"https://photos.example.com"}):
            result=app.instagram_configuration()
        self.assertNotIn("INSTAGRAM_ACCESS_TOKEN",result["invalid"])
        self.assertTrue(result["ready"])

    def test_auto_routes_but_does_not_claim_authentication(self):
        with patch.dict(os.environ,{"INSTAGRAM_LOGIN_TYPE":"auto","INSTAGRAM_ACCESS_TOKEN":"EAA-test"}):
            self.assertEqual(app.instagram_login_type(),"unified")
        with patch.dict(os.environ,{"INSTAGRAM_LOGIN_TYPE":"auto","INSTAGRAM_ACCESS_TOKEN":"IGAA-test"}):
            self.assertEqual(app.instagram_login_type(),"instagram")

    def test_opaque_token_requires_explicit_mode_instead_of_wrong_host(self):
        with patch.dict(os.environ,{"INSTAGRAM_LOGIN_TYPE":"auto","INSTAGRAM_ACCESS_TOKEN":"opaque-token","INSTAGRAM_ACCOUNT_ID":"123","PUBLIC_MEDIA_BASE_URL":"https://photos.example.com"}),patch.object(app,"remote") as remote:
            self.assertEqual(app.instagram_login_type(),"unknown")
            self.assertIn("INSTAGRAM_LOGIN_TYPE",app.instagram_configuration()["invalid"])
            with self.assertRaisesRegex(app.Problem,"자동으로 구분하지 못했어요"):app.graph("me?fields=id")
            remote.assert_not_called()

    def test_explicit_unified_accepts_opaque_tokens_and_keeps_threads_separate(self):
        with patch.dict(os.environ,{"INSTAGRAM_LOGIN_TYPE":"unified","INSTAGRAM_ACCESS_TOKEN":"opaque-token","THREADS_ACCESS_TOKEN":"different-threads-token"}),patch.object(app,"remote",return_value={"id":"123"}) as remote:
            app.graph("123?fields=id")
        self.assertTrue(remote.call_args.args[0].startswith("https://graph.facebook.com/"))
        self.assertEqual(remote.call_args.args[2],"opaque-token")
