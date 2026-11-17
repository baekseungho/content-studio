import base64
import io
import json
import os
from pathlib import Path
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch
import urllib.error
import urllib.request

TMP = tempfile.TemporaryDirectory(prefix="dajeong-tests-")
os.environ["STUDIO_DATA_DIR"] = TMP.name
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import app
from PIL import Image

def sample():
    b = io.BytesIO()
    Image.new("RGB", (300, 200), "#93ad7f").save(b, "PNG")
    return app.upload({"data":base64.b64encode(b.getvalue()).decode()})["id"]

class StudioTests(unittest.TestCase):
    def setUp(self):
        self.mid = sample()
        self.draft = app.save_draft({"title":"제목 <script>", "blog":"## 소제목\n본문 <script>alert(1)</script>\n[[photo:1]]",
            "instagram":"사진 이야기 #일상", "images":[self.mid]})

    def test_photo_normalized_and_metadata_removed(self):
        with Image.open(app.MEDIA / (self.mid + ".jpg")) as image:
            self.assertEqual(image.format, "JPEG")
            self.assertEqual(image.size, (300,200))
            self.assertFalse(image.getexif())

    def test_invalid_photo_and_path(self):
        for bad in ("bad", base64.b64encode(b"not an image").decode()):
            with self.assertRaises(app.Problem):
                app.upload({"data":bad})
        with self.assertRaises(app.Problem):
            app.image_ids(["../app"])
        with self.assertRaises(app.Problem):
            app.image_ids([self.mid]*11)

    def test_roundtrip_and_update(self):
        self.assertEqual(app.get_draft(self.draft["id"])["images"], [self.mid])
        updated=app.save_draft({**self.draft,"title":"수정"})
        self.assertEqual(app.get_draft(updated["id"])["title"],"수정")

    def test_export_escapes_html_and_embeds_image(self):
        output=app.blog_html(self.draft)
        self.assertNotIn("<script>alert",output)
        self.assertIn("&lt;script&gt;",output)
        self.assertIn("<h2>소제목</h2>",output)
        self.assertEqual(output.count("data:image/jpeg;base64,"),1)

    def test_required_story_is_saved_in_caption_and_cannot_overflow_silently(self):
        body={"title":"제목","blog":"본문","instagram":"온천 후기\n\n#부산","facts":"욕실용품은 바이레도였어요.","images":[self.mid]}
        saved=app.save_draft(body)
        self.assertIn(body["facts"],saved["instagram"])
        self.assertEqual(app.save_draft(saved)["instagram"],saved["instagram"])
        body["facts"]="중요한 이야기"*400
        with self.assertRaisesRegex(app.Problem,"2,200"):
            app.save_draft(body)

    def test_caption_limit(self):
        with self.assertRaises(app.Problem):
            app.save_draft({**self.draft,"instagram":"가"*2201})

    def test_generate_uses_images_and_verified_search_sources(self):
        generated={"title":"새 제목","blog":"새 본문\n[[photo:1]]","instagram":"짧은 글",
                   "sources":[{"url":"https://hallucinated.invalid","title":"가짜"}]}
        response={"output":[{"type":"web_search_call","action":{"sources":[{"url":"https://example.com/real","title":"실제 출처"}]}},
            {"type":"message","content":[{"type":"output_text","text":json.dumps(generated),"annotations":[]}]}]}
        with patch.dict(os.environ,{"OPENAI_API_KEY":"test-key"}), patch.object(app,"remote",return_value=response) as request:
            result=app.generate({"prompt":"카페 소개","research":True,"images":[self.mid]})
        self.assertEqual(result["sources"],[{"url":"https://example.com/real","title":"실제 출처"}])
        payload=request.call_args.args[1]
        self.assertFalse(payload["store"])
        self.assertTrue(next(part["image_url"] for part in payload["input"][0]["content"] if part["type"]=="input_image").startswith("data:image/jpeg;"))
        photo_context=json.loads(payload["input"][0]["content"][1]["text"])
        self.assertEqual(photo_context["photo_number"],1)
        self.assertEqual(photo_context["marker"],"[[photo:1]]")
        self.assertEqual(payload["tools"],[{"type":"web_search"}])

    def test_generate_requires_key_and_actual_search(self):
        with patch.dict(os.environ,{"OPENAI_API_KEY":""}):
            with self.assertRaises(app.Problem):
                app.generate({"prompt":"내용"})
        response={"output":[{"type":"message","content":[{"type":"output_text","text":'{"title":"T","blog":"B","instagram":"I"}'}]}]}
        with patch.dict(os.environ,{"OPENAI_API_KEY":"test"}),patch.object(app,"remote",return_value=response):
            with self.assertRaises(app.Problem):
                app.generate({"prompt":"내용","research":True})

    def test_instagram_publish_and_duplicate_guard(self):
        def fake(path,payload=None):
            if "status_code" in path:
                return {"status_code":"FINISHED"}
            return {"id":"published-id" if path.endswith("media_publish") else "container-id"}
        config={"INSTAGRAM_ACCOUNT_ID":"123","INSTAGRAM_ACCESS_TOKEN":"test","PUBLIC_MEDIA_BASE_URL":"https://photos.example.com"}
        with patch.dict(os.environ,config),patch.object(app,"graph",side_effect=fake):
            result=app.publish_instagram(self.draft["id"])
            self.assertEqual(result["media_id"],"published-id")
            with self.assertRaises(app.Problem):
                app.publish_instagram(self.draft["id"])
        with Image.open(app.MEDIA / (self.mid+"-ig.jpg")) as image:
            self.assertEqual(image.size,(1080,1350))

    def test_carousel_flow(self):
        d=app.save_draft({**self.draft,"images":[self.mid,sample()]})
        calls=[]
        def fake(path,payload=None):
            calls.append((path,payload))
            return {"status_code":"FINISHED"} if "status_code" in path else {"id":str(len(calls))}
        with patch.dict(os.environ,{"INSTAGRAM_ACCOUNT_ID":"123","INSTAGRAM_ACCESS_TOKEN":"test","PUBLIC_MEDIA_BASE_URL":"https://photos.example.com"}),patch.object(app,"graph",side_effect=fake):
            app.publish_instagram(d["id"])
        carousel=[body for _,body in calls if body and body.get("media_type")=="CAROUSEL"]
        self.assertEqual(len(carousel),1)
        self.assertEqual(len(carousel[0]["children"].split(",")),2)

    def test_publish_response_loss_blocks_retry(self):
        def fake(path,payload=None):
            if path.endswith("media_publish"):
                raise app.Problem("timeout",502)
            return {"status_code":"FINISHED"} if "status_code" in path else {"id":"container"}
        with patch.dict(os.environ,{"INSTAGRAM_ACCOUNT_ID":"123","INSTAGRAM_ACCESS_TOKEN":"test","PUBLIC_MEDIA_BASE_URL":"https://photos.example.com"}),patch.object(app,"graph",side_effect=fake):
            with self.assertRaises(app.Problem):
                app.publish_instagram(self.draft["id"])
            with app.db() as c:
                self.assertEqual(c.execute("SELECT state FROM attempts WHERE draft_id=?",(self.draft["id"],)).fetchone()[0],"uncertain")
            with self.assertRaises(app.Problem):
                app.publish_instagram(self.draft["id"])

    def test_pre_publish_failure_allows_retry(self):
        config={"INSTAGRAM_ACCOUNT_ID":"123","INSTAGRAM_ACCESS_TOKEN":"test","PUBLIC_MEDIA_BASE_URL":"https://photos.example.com"}
        with patch.dict(os.environ,config),patch.object(app,"graph",side_effect=app.Problem("bad media",502)):
            with self.assertRaises(app.Problem):
                app.publish_instagram(self.draft["id"])
            with self.assertRaises(app.Problem):
                app.publish_instagram(self.draft["id"])
        with app.db() as c:
            self.assertEqual(c.execute("SELECT COUNT(*) FROM attempts WHERE draft_id=? AND state='failed'",(self.draft["id"],)).fetchone()[0],2)

class HttpTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server=app.ThreadingHTTPServer(("127.0.0.1",0),app.Handler)
        cls.port=cls.server.server_address[1]
        app.HOSTS.add("127.0.0.1:"+str(cls.port))
        cls.thread=threading.Thread(target=cls.server.serve_forever,daemon=True)
        cls.thread.start()
        cls.base="http://127.0.0.1:"+str(cls.port)

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join()

    def test_http_csrf_host_and_private_files(self):
        req=urllib.request.Request(self.base+"/api/drafts",data=b"{}",headers={"Content-Type":"application/json"})
        with self.assertRaises(urllib.error.HTTPError) as e:
            urllib.request.urlopen(req)
        self.assertEqual(e.exception.code,403)
        e.exception.close()
        req=urllib.request.Request(self.base+"/api/status",headers={"Host":"evil.example"})
        with self.assertRaises(urllib.error.HTTPError) as e:
            urllib.request.urlopen(req)
        self.assertEqual(e.exception.code,403)
        e.exception.close()
        for path in ("/.env","/data/studio.db","/media/../../.env"):
            with self.assertRaises(urllib.error.HTTPError) as e:
                urllib.request.urlopen(self.base+path)
            self.assertEqual(e.exception.code,404)
            e.exception.close()

    def test_threads_publish_requires_explicit_confirmation(self):
        req=urllib.request.Request(self.base+"/api/publish/threads",data=json.dumps({"id":"a"*32}).encode(),headers={"Content-Type":"application/json","X-Studio-Token":app.TOKEN})
        with patch.object(app,"start_job") as start:
            with self.assertRaises(urllib.error.HTTPError) as error:urllib.request.urlopen(req)
            self.assertEqual(error.exception.code,400);error.exception.close();start.assert_not_called()

    def test_http_save_load_and_token_injection(self):
        with urllib.request.urlopen(self.base) as response:
            self.assertIn(app.TOKEN.encode(),response.read())
        req=urllib.request.Request(self.base+"/api/drafts",data=json.dumps({"title":"HTTP 테스트"}).encode(),
            headers={"Content-Type":"application/json","X-Studio-Token":app.TOKEN})
        with urllib.request.urlopen(req) as response:
            result=json.load(response)
        with urllib.request.urlopen(self.base+"/api/drafts/"+result["id"]) as response:
            self.assertEqual(json.load(response)["title"],"HTTP 테스트")

def tearDownModule():
    TMP.cleanup()

if __name__=="__main__":
    unittest.main()
