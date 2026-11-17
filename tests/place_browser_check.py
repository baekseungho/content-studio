"""Place selection UI against an isolated real local server; no live AI/publication."""
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
with tempfile.TemporaryDirectory(prefix="mellow-place-browser-") as directory:
    env={**os.environ,"PORT":"8879","STUDIO_DATA_DIR":directory,"OPENAI_API_KEY":"","NAVER_SEARCH_CLIENT_ID":"","NAVER_SEARCH_CLIENT_SECRET":""}
    process=subprocess.Popen([sys.executable,str(ROOT/"app.py")],cwd=ROOT,env=env,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
    try:
        for _ in range(60):
            try:
                urllib.request.urlopen("http://127.0.0.1:8879/api/status",timeout=1).close();break
            except Exception:time.sleep(.2)
        else:raise RuntimeError("Test server not ready")
        with sync_playwright() as p:
            browser=p.chromium.launch(headless=True)
            page=browser.new_page(viewport={"width":1440,"height":1100})
            errors=[];page.on("pageerror",lambda error:errors.append(str(error)))
            page.goto("http://127.0.0.1:8879")
            expect(page.locator("#selectedPlace")).to_be_hidden()
            expect(page.locator("#placePanel")).not_to_have_attribute("open","")
            page.locator("#placePanel>summary").click();page.locator("#placeManual>summary").click()
            page.locator("#placeUseManual").click();expect(page.locator("#selectedPlace")).to_be_hidden()
            page.locator("#placeName").fill("샘플카페 성수점");page.locator("#placeAddress").fill("서울특별시 성동구 성수일로 12-3")
            page.locator("#placeUseManual").click();expect(page.locator("#selectedPlaceName")).to_have_text("샘플카페 성수점")
            page.locator("#placeClear").click();expect(page.locator("#selectedPlace")).to_be_hidden()
            # Distinguish same-name venues by address, and render candidate names as text.
            places=[{"name":"같은이름","address":"부산 해운대구 해운대해변로 296"},{"name":"같은이름","address":"서울 성동구 성수일로 12-3"},{"name":"<img src=x onerror=alert(1)>","address":"서울 성동구 성수일로 14"}]
            page.route("**/api/places/search",lambda route:route.fulfill(json={"job":"place-test"}))
            page.route("**/api/jobs/place-test",lambda route:route.fulfill(json={"state":"done","result":{"places":places,"notice":"주소를 보고 선택해 주세요."}}))
            page.locator("#placePanel>summary").click();page.locator("#placeQuery").fill("성수 같은이름");page.locator("#placeSearch").click()
            expect(page.locator("#placeSearch")).to_be_disabled()
            expect(page.locator(".place-result")).to_have_count(3)
            expect(page.locator(".place-result img")).to_have_count(0)
            page.locator(".place-result").nth(1).get_by_role("button").click()
            expect(page.locator("#selectedPlaceAddress")).to_have_text("서울 성동구 성수일로 12-3")
            page.locator("#moreOptions>summary").click();page.locator("#research").check()
            expect(page.locator("#placeContextHint")).to_contain_text("기준으로 검색")
            page.locator("#prompt").fill("창가에서 쉬었던 기록")
            page.locator("#manualStart").click();page.locator("#title").fill("장소를 담은 기록");page.locator("#body").fill("내가 직접 적은 이야기")
            page.locator("#save").click();expect(page.locator("#saveState")).to_have_text("저장 완료")
            rows=page.request.get("http://127.0.0.1:8879/api/drafts").json()
            saved=page.request.get("http://127.0.0.1:8879/api/drafts/"+rows[0]["id"]).json()
            assert saved["selected_place"]["address"]=="서울 성동구 성수일로 12-3" and saved["research"] is True
            page.locator("#newDraft").click();expect(page.locator("#selectedPlace")).to_be_hidden();expect(page.locator("#research")).not_to_be_checked()
            page.locator("#showDrafts").click();page.locator(".draft-row").first.click();expect(page.locator("#modal")).to_be_hidden()
            expect(page.locator("#selectedPlaceName")).to_have_text("같은이름");expect(page.locator("#research")).to_be_checked()
            # Changing the place preserves existing prose and warns that regeneration is needed.
            page.locator("#placeClear").click();expect(page.locator("#placeContextHint")).to_contain_text("이미 만든 글은 그대로")
            page.on("dialog",lambda dialog:dialog.accept())
            page.reload();expect(page.locator("#selectedPlace")).to_be_hidden();expect(page.locator("#research")).to_be_checked()
            page.locator("#placePanel>summary").click();page.locator("#placeManual>summary").click();page.locator("#placeName").fill("긴 이름의 카페 성수점");page.locator("#placeAddress").fill("서울특별시 성동구 성수일로 12-3 아주 긴 이름의 건물 101호")
            page.locator("#placeUseManual").click()
            for width in (320,390,768,1440):
                page.set_viewport_size({"width":width,"height":1000})
                assert page.evaluate("document.documentElement.scrollWidth<=innerWidth"),width
            qa=ROOT/"data/qa";qa.mkdir(parents=True,exist_ok=True)
            page.screenshot(path=str(qa/"place-selection.png"),full_page=True)
            # Real endpoint denies requests without the local token; no actual web request is made.
            denied=page.request.post("http://127.0.0.1:8879/api/places/search",data=json.dumps({"query":"test"}),headers={"Content-Type":"application/json"})
            assert denied.status==403
            assert not errors,errors
            browser.close()
        print("Place browser: selection, address distinction, XSS, save/reopen, recovery, optional reset, mobile and auth passed")
    finally:
        process.terminate();process.wait(timeout=10)
