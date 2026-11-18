"""Selected-platform UX; isolated storage, mocked AI, no real publication."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import urllib.request
from playwright.sync_api import sync_playwright,expect
ROOT=Path(__file__).resolve().parents[1]
with tempfile.TemporaryDirectory(prefix="mellow-platform-browser-") as directory:
    env={**os.environ,"PORT":"8880","STUDIO_DATA_DIR":directory,"OPENAI_API_KEY":"mock-key"}
    process=subprocess.Popen([sys.executable,str(ROOT/"app.py")],cwd=ROOT,env=env,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
    try:
        for _ in range(60):
            try:urllib.request.urlopen("http://127.0.0.1:8880/api/status",timeout=1).close();break
            except Exception:time.sleep(.2)
        else:raise RuntimeError("Test server not ready")
        with sync_playwright() as p:
            browser=p.chromium.launch(headless=True);page=browser.new_page(viewport={"width":1440,"height":1100});page.on("dialog",lambda dialog:dialog.accept())
            errors=[];page.on("pageerror",lambda error:errors.append(str(error)))
            requests=[];jobs={};failed=[False]
            def generate(route):
                body=route.request.post_data_json;requests.append(body);number=len(requests);job="platform-"+str(number);answer={}
                for platform in body["platforms"]:
                    if platform=="naver":answer.update(title="네이버 제목 "+str(number),blog="네이버 전용 원고 "+str(number))
                    if platform=="tistory":answer.update(tistory_title="티스토리 제목 "+str(number),tistory="티스토리 전용 원고 "+str(number))
                    if platform=="instagram":answer.update(instagram="인스타그램 전용 글 "+str(number))
                    if platform=="threads":answer.update(threads="스레드 전용 글 "+str(number))
                if number==1:answer["blog"]="미선택 원고를 덮어쓰면 안 됨"
                jobs[job]={"state":"failed","error":"일시적인 연결 오류"} if failed[0] else {"state":"done","result":answer}
                route.fulfill(json={"job":job})
            page.route("**/api/generate",generate);page.route("**/api/jobs/platform-*",lambda route:route.fulfill(json=jobs[route.request.url.rsplit("/",1)[-1]]))
            page.goto("http://127.0.0.1:8880");page.wait_for_function("status.ai===true")
            page.locator("#prompt").fill("카페 창가에서 커피 마시며 쉬었어")
            page.locator("#generate").click();expect(page.locator(".platform-choices input:checked")).to_have_count(1)
            expect(page.locator("#platformChoice-naver")).to_be_checked()
            page.locator("#platformChoice-naver").uncheck();expect(page.locator("#startSelectedGeneration")).to_be_disabled();assert not requests
            page.locator("#closeModal").click();assert not requests
            page.locator("#generate").click();page.locator("#platformChoice-naver").uncheck();page.locator("#platformChoice-instagram").check();page.locator("#startSelectedGeneration").click()
            expect(page.locator("#writingProgress")).to_have_attribute("data-state","done");expect(page.locator("#generate")).to_be_enabled()
            expect(page.locator("#instaTab")).to_have_attribute("aria-selected","true");assert page.evaluate("draft.blog")=="";assert page.evaluate("draft.tistory")==""
            first=page.evaluate("draft.instagram");assert requests[0]["platforms"]==["instagram"]
            assert all(key not in requests[0] for key in ("blog","tistory","threads","title","instagram"))
            page.locator("#blogTab").click();expect(page.locator("#modalTitle")).to_contain_text("네이버")
            expect(page.locator(".platform-choices input")).to_have_count(1);page.locator("#closeModal").click();expect(page.locator("#platformEmpty")).to_be_visible();assert len(requests)==1
            page.locator("#platformGenerate").click();page.locator("#startSelectedGeneration").click();expect(page.locator("#generate")).to_be_enabled();expect(page.locator("#preview")).to_contain_text("네이버 전용 원고")
            assert page.evaluate("draft.instagram")==first;naver=page.evaluate("draft.blog");naver_title=page.evaluate("draft.title")
            page.locator("#tistoryTab").click();expect(page.locator(".platform-choices input")).to_have_count(1);page.locator("#startSelectedGeneration").click()
            expect(page.locator("#preview")).to_contain_text("티스토리 전용 원고");expect(page.locator("#generate")).to_be_enabled()
            tistory=page.evaluate("draft.tistory");assert page.evaluate("draft.blog")==naver
            page.locator("#blogTab").click();expect(page.locator("#preview")).to_contain_text(naver);assert page.locator("#title").input_value()==naver_title
            failed[0]=True;page.locator("#threadsTab").click();page.locator("#startSelectedGeneration").click();expect(page.locator("#writingProgress")).to_have_attribute("data-state","error")
            expect(page.locator("#generate")).to_be_enabled();assert page.evaluate("draft.instagram")==first and page.evaluate("draft.blog")==naver and page.evaluate("draft.tistory")==tistory
            failed[0]=False;page.locator("#platformGenerate").click();page.locator("#startSelectedGeneration").click();expect(page.locator("#preview")).to_contain_text("스레드 전용 글");expect(page.locator("#generate")).to_be_enabled()
            count=len(requests);page.locator("#instaTab").click();expect(page.locator("#modal")).to_be_hidden();assert len(requests)==count
            page.locator("#save").click();expect(page.locator("#saveState")).to_have_text("저장 완료")
            page.locator("#tistoryTab").click()
            page.locator("#resultTools").evaluate("el=>el.open=true")
            with page.expect_download() as downloaded:page.locator("#export").click()
            downloaded_html=Path(downloaded.value.path()).read_text(encoding="utf-8")
            assert tistory in downloaded_html and naver not in downloaded_html
            page.locator("#newDraft").click();page.locator("#showDrafts").click();page.locator(".draft-row").first.click();expect(page.locator("#modal")).to_be_hidden()
            assert page.evaluate("draft.blog")==naver and page.evaluate("draft.tistory")==tistory and page.evaluate("draft.instagram")==first
            page.locator("#tistoryTab").click();expect(page.locator("#preview")).to_contain_text(tistory)
            for width in (320,390,768,1440):
                page.set_viewport_size({"width":width,"height":1000});assert page.evaluate("document.documentElement.scrollWidth<=innerWidth"),width
            page.locator("#generate").click()
            for width in (320,390,768,1440):
                page.set_viewport_size({"width":width,"height":1000});assert page.evaluate("document.documentElement.scrollWidth<=innerWidth"),width
            qa=ROOT/"data/qa";qa.mkdir(exist_ok=True);page.screenshot(path=str(qa/"platform-picker.png"),full_page=True)
            assert not errors,errors;browser.close()
            print("Platform browser passed: explicit selection, cancel/zero cost, isolated requests, per-tab addition, failure preservation, independent blogs, save/reopen and mobile")
    finally:process.terminate();process.wait(timeout=10)
