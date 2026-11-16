"""Naver editor regressions using a local DOM fixture; never contacts Naver."""
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
from PIL import Image
from playwright.sync_api import sync_playwright
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import app
import naver_bridge
from naver_bridge import find_editor, editor_text, fill_editor, BridgeError

FIXTURE = """<!doctype html><html><body>
<style>.se-text-paragraph{min-height:26px}.se-section-text{min-height:60px}</style><div contenteditable="true">
 <div class="se-section-documentTitle"><p class="se-text-paragraph"><span class="se-placeholder" contenteditable="false">제목</span></p></div>
 <div class="se-section-text"><p class="se-text-paragraph"><span class="se-placeholder" contenteditable="false">글감과 함께 나의 일상을 기록해보세요!</span></p></div>
</div>
<input type="file" multiple accept="image/*" style="display:none">
<script>
document.querySelectorAll('.se-placeholder').forEach(el=>el.addEventListener('mousedown',e=>e.preventDefault()));
document.addEventListener('input',()=>{
 document.querySelectorAll('.se-placeholder').forEach(el=>el.remove());
});
document.querySelector('input[type=file]').addEventListener('change',()=>{
 for(const file of document.querySelector('input[type=file]').files){let image=document.createElement('div');image.className='se-component se-image';image.tabIndex=0;image.contentEditable='false';
 image.style='display:block;width:100px;height:60px;background:#91a979';image.textContent='사진';
 const img=document.createElement('img');img.className='se-image-resource';img.src=URL.createObjectURL(file);image.append(img);document.querySelector('.se-section-text').append(image);}
});
</script>
</body></html>"""

class NaverEditorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp=tempfile.TemporaryDirectory(prefix="naver-fixture-")
        cls.media=Path(cls.temp.name)
        cls.patches=[patch.object(app,"MEDIA",cls.media),patch.object(naver_bridge,"MEDIA",cls.media)]
        for item in cls.patches:
            item.start()
        cls.playwright=sync_playwright().start()
        cls.browser=cls.playwright.chromium.launch(headless=True)
    @classmethod
    def tearDownClass(cls):
        cls.browser.close()
        cls.playwright.stop()
        for item in cls.patches:
            item.stop()
        cls.temp.cleanup()
    def setUp(self):
        self.context=self.browser.new_context()
        self.page=self.context.new_page()
        self.page.set_content(FIXTURE)
    def tearDown(self):
        self.context.close()

    def test_inherited_editability_and_placeholders(self):
        self.assertEqual(self.page.locator(".se-section-documentTitle [contenteditable=true]").count(),0)
        found=find_editor(self.context)
        self.assertIsNotNone(found)
        self.assertEqual(editor_text(found[2]),"")
        reports=[]
        draft={"title":"주말의 기록","blog":"## 소제목\n첫 번째 문장\n둘째 문장","images":[],"sources":[]}
        fill_editor(*found,draft,lambda state,message:reports.append((state,message)))
        self.assertEqual(editor_text(found[2]),draft["title"])
        self.assertIn("첫 번째 문장",editor_text(found[3]))
        self.assertIn("둘째 문장",editor_text(found[3]))
        self.assertGreaterEqual(len(reports),2)

    def test_iframe_editor_detection(self):
        self.page.set_content("<iframe></iframe>")
        frame=self.page.frames[1]
        frame.set_content(FIXTURE)
        found=find_editor(self.context)
        self.assertIsNotNone(found)
        self.assertEqual(found[1],frame)

    def test_existing_content_not_overwritten(self):
        self.page.locator(".se-section-documentTitle").evaluate("el=>el.textContent='기존 제목'")
        found=find_editor(self.context)
        with self.assertRaises(BridgeError):
            fill_editor(*found,{"title":"덮어쓰기","blog":"본문","images":[],"sources":[]},lambda *args:None)
        self.assertEqual(editor_text(found[2]),"기존 제목")

    def test_photo_file_input(self):
        image=io.BytesIO()
        Image.new("RGB",(80,60),"#a0b581").save(image,"PNG")
        mid=app.upload({"data":base64.b64encode(image.getvalue()).decode()})["id"]
        found=find_editor(self.context)
        draft={"title":"사진 기록","blog":"사진을 담아요.\n[[photo:1]]","images":[mid],"sources":[]}
        fill_editor(*found,draft,lambda *args:None)
        self.assertEqual(self.page.locator(".se-component.se-image").count(),1)

    def test_multiple_photos_uploaded_in_one_selection(self):
        mids=[]
        for color in ("red","blue"):
            image=io.BytesIO()
            Image.new("RGB",(80,60),color).save(image,"PNG")
            mids.append(app.upload({"data":base64.b64encode(image.getvalue()).decode()})["id"])
        self.page.evaluate("window.photoChanges=0;document.querySelector('input[type=file]').addEventListener('change',()=>window.photoChanges++)")
        found=find_editor(self.context)
        draft={"title":"사진 두 장","blog":"첫 문단\n[[photo:1]]\n둘째 문단\n[[photo:2]]","images":mids,"sources":[]}
        fill_editor(*found,draft,lambda *args:None)
        self.assertEqual(naver_bridge.loaded_photo_count(found[1]),2)
        self.assertEqual(self.page.evaluate("window.photoChanges"),1)

    def test_account_protection_stops_and_locks(self):
        self.page.set_content("<p>네이버 계정 보호조치 안내</p>")
        with patch.object(naver_bridge,"DATA",self.media):
            with self.assertRaises(BridgeError):
                naver_bridge.check_protection(self.context)
            from naver_guard import NaverGuard
            self.assertTrue(NaverGuard(self.media/"naver-guard.json").status()["blocked"])

class ConnectionTests(unittest.TestCase):
    def test_missing_media_url_identified_without_secret_values(self):
        with patch.dict(os.environ,{"INSTAGRAM_ACCOUNT_ID":"123","INSTAGRAM_ACCESS_TOKEN":"secret-value","PUBLIC_MEDIA_BASE_URL":""}):
            result=app.instagram_configuration()
        self.assertEqual(result["missing"],["PUBLIC_MEDIA_BASE_URL"])
        self.assertNotIn("secret-value",json.dumps(result))
        self.assertFalse(result["ready"])

    def test_invalid_public_url(self):
        for url in ("http://example.com","https://localhost","https://127.0.0.1","https://example.com?token=secret"):
            with patch.dict(os.environ,{"INSTAGRAM_ACCOUNT_ID":"123","INSTAGRAM_ACCESS_TOKEN":"test","PUBLIC_MEDIA_BASE_URL":url}):
                self.assertFalse(app.instagram_configuration()["ready"])

    def test_job_progress(self):
        release=threading.Event()
        def work(progress):
            progress("로그인 대기")
            release.wait(3)
            return {"ok":True}
        jid=app.start_job(work,with_progress=True)["job"]
        try:
            import time
            for _ in range(100):
                with app.JOB_LOCK:
                    value=app.JOBS[jid].copy()
                if value.get("message")=="로그인 대기":
                    break
                time.sleep(.01)
            self.assertEqual(value["message"],"로그인 대기")
        finally:
            release.set()

if __name__=="__main__":
    unittest.main()
