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
