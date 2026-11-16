import io
import json
import unittest
from unittest.mock import patch
import urllib.error
import app

class AuthenticationErrors(unittest.TestCase):
    def test_instagram_oauth_error_is_actionable_and_redacted(self):
        payload=json.dumps({"error":{"code":190,"message":"bad secret-token-value"}}).encode()
        error=urllib.error.HTTPError("https://graph.instagram.com/v27.0/me",401,"Unauthorized",{},io.BytesIO(payload))
        with patch.object(app.urllib.request,"urlopen",side_effect=error):
            with self.assertRaises(app.Problem) as result:
                app.remote("https://graph.instagram.com/v27.0/me",token="secret-token-value")
        self.assertIn("INSTAGRAM_ACCESS_TOKEN",result.exception.message)
        self.assertNotIn("secret-token-value",result.exception.message)

    def test_openai_auth_error_names_correct_setting(self):
        error=urllib.error.HTTPError("https://api.openai.com/v1/responses",401,"Unauthorized",{},io.BytesIO(b"{}"))
        with patch.object(app.urllib.request,"urlopen",side_effect=error):
            with self.assertRaises(app.Problem) as result:
                app.remote("https://api.openai.com/v1/responses",token="secret")
        self.assertIn("OPENAI_API_KEY",result.exception.message)
