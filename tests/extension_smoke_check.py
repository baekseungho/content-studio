"""실제 확장 로딩·로컬 API 연결 검증. 네이버에는 접속하지 않는다."""
import base64
import io
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import time
import urllib.request
import urllib.error
from PIL import Image
from playwright.sync_api import sync_playwright
ROOT=Path(__file__).resolve().parents[1]
with tempfile.TemporaryDirectory(prefix="extension-smoke-") as temp:
    env={**os.environ,"PORT":"8877","STUDIO_DATA_DIR":str(Path(temp)/"data"),
         "OPENAI_API_KEY":"","INSTAGRAM_ACCESS_TOKEN":"","NAVER_BLOG_ID":"test_fixture"}
    process=subprocess.Popen([sys.executable,str(ROOT/"app.py")],cwd=ROOT,env=env,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
    base="http://127.0.0.1:8877"
    try:
        for _ in range(60):
            try:
                with urllib.request.urlopen(base) as response:
                    html=response.read().decode("utf-8-sig")
                break
            except Exception:
                time.sleep(.2)
        else:
            raise RuntimeError("Test server not ready")
        token=re.search(r'<meta(?=[^>]*name="studio-token")(?=[^>]*content="([^"]+)")[^>]*>',html)[1]
        def post(path,body):
            request=urllib.request.Request(base+path,data=json.dumps(body).encode(),
                headers={"Content-Type":"application/json","X-Studio-Token":token})
            with urllib.request.urlopen(request) as response:
                return json.load(response)
        image=io.BytesIO();Image.new("RGB",(8,8),"green").save(image,"PNG")
        photo=post("/api/upload",{"data":base64.b64encode(image.getvalue()).decode()})["id"]
        draft=post("/api/drafts",{"title":"확장 연결 테스트","blog":"본문","images":[photo]})
        handoff=post("/api/naver/handoff",{"id":draft["id"]})
        hostile=urllib.request.Request(base+"/api/extension/redeem",data=json.dumps({"code":handoff["code"]}).encode(),
            headers={"Content-Type":"application/json","Origin":"https://evil.example","X-Dajeong-Extension":"1"})
        try:
            urllib.request.urlopen(hostile)
            raise AssertionError("Hostile origin accepted")
        except urllib.error.HTTPError as error:
            assert error.code==403
            error.close()
        with sync_playwright() as p:
            extension=str(ROOT/"chrome-extension")
            context=p.chromium.launch_persistent_context(str(Path(temp)/"browser"),channel="chromium",headless=True,
                args=["--disable-extensions-except="+extension,"--load-extension="+extension])
            try:
                worker=context.service_workers[0] if context.service_workers else context.wait_for_event("serviceworker")
                extension_id=worker.url.split("/")[2]
                page=context.new_page()
                page.goto("chrome-extension://"+extension_id+"/popup.html")
                assert page.locator("#fill").is_visible()
                payload=page.evaluate("""async args=>{
                  const response=await fetch(args.base+'/api/extension/redeem',{method:'POST',
                    headers:{'Content-Type':'application/json','X-Dajeong-Extension':'1'},body:JSON.stringify({code:args.code})});
                  return {status:response.status,body:await response.json()};
                }""",{"base":base,"code":handoff["code"]})
                assert payload["status"]==200,payload
                assert payload["body"]["expected_photos"]==1
                assert len(payload["body"]["photos"])==1
                assert "access_token" not in payload["body"]
                result=page.evaluate("""async args=>{
                  const response=await fetch(args.base+'/api/extension/report',{method:'POST',
                    headers:{'Content-Type':'application/json','X-Dajeong-Extension':'1'},
                    body:JSON.stringify({token:args.token,state:'ready',count:1})});return response.status;
                }""",{"base":base,"token":payload["body"]["report_token"]})
                assert result==200,result
                qa=ROOT/"data"/"qa";qa.mkdir(parents=True,exist_ok=True)
                page.screenshot(path=str(qa/"extension-popup.png"))
            finally:
                context.close()
        print("Extension loaded; popup rendered; actual cross-origin handoff/report succeeded; hostile origin rejected. No Naver access or publishing.")
    finally:
        process.terminate();process.wait(timeout=10)
