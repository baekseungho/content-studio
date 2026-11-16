"""로컬 앱 실제 브라우저 검증. 실제 AI/SNS 호출은 하지 않는다."""
import io
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import urllib.request
from PIL import Image
from playwright.sync_api import sync_playwright, expect

ROOT=Path(__file__).resolve().parents[1]
QA=ROOT/"data"/"qa"
QA.mkdir(parents=True,exist_ok=True)
with tempfile.TemporaryDirectory(prefix="dajeong-browser-") as temp:
    env={**os.environ,"PORT":"8877","STUDIO_DATA_DIR":temp,"OPENAI_API_KEY":"",
         "INSTAGRAM_ACCOUNT_ID":"","INSTAGRAM_ACCESS_TOKEN":"","PUBLIC_MEDIA_BASE_URL":"","NAVER_BLOG_ID":"test_fixture"}
    process=subprocess.Popen([sys.executable,str(ROOT/"app.py")],cwd=ROOT,env=env,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
    try:
        for _ in range(60):
            try:
                with urllib.request.urlopen("http://127.0.0.1:8877/api/status",timeout=1):
                    break
            except Exception:
                time.sleep(.2)
        else:
            raise RuntimeError("Server not ready")
        with sync_playwright() as p:
            browser=p.chromium.launch(headless=True)
            page=browser.new_page(viewport={"width":1440,"height":1120},device_scale_factor=1)
            errors=[]
            page.on("pageerror",lambda e:errors.append(str(e)))
            page.goto("http://127.0.0.1:8877")
            page.locator("#connectionNotice").wait_for(state="visible")
            expect(page.locator("#workflow")).to_have_attribute("data-stage","1")
            expect(page.locator('.step-button[data-step="2"]')).to_be_disabled()
            page.screenshot(path=str(QA/"desktop-home.png"),full_page=True)
            for width,height in ((320,844),(768,1024),(1024,900),(1920,1080)):
                page.set_viewport_size({"width":width,"height":height})
                assert page.evaluate("document.documentElement.scrollWidth<=window.innerWidth"),width
            page.set_viewport_size({"width":1440,"height":1120})
            assert page.locator("#newDraft").bounding_box()["y"]-page.locator(".brand").bounding_box()["y"]>=95
            page.locator("#settingsButton").click()
            expect(page.locator("#modal")).to_be_visible()
            page.locator("#closeModal").click()
            image=io.BytesIO()
            Image.new("RGB",(800,600),"#9caa83").save(image,"PNG")
            page.locator("#photos").set_input_files({"name":"sample.png","mimeType":"image/png","buffer":image.getvalue()})
            expect(page.locator(".photo")).to_have_count(1)
            expect(page.locator("#photos")).to_be_enabled()
            expect(page.locator("#tone option")).to_have_count(17)
            page.locator("#tone").select_option(label="짧고 위트 있게")
            expect(page.locator("#toneGuide")).to_contain_text("언어유희")
            page.locator("#prompt").fill("주말의 작은 여유를 기록해 줘.")
            page.locator("#moreOptions > summary").click()
            page.locator("#facts").fill("직접 따뜻한 차를 마시며 쉬었다.")
            page.locator("#disclosure").select_option("gifted")
            page.locator("#manualStart").click()
            expect(page.locator("#workflow")).to_have_attribute("data-stage","2")
            page.locator("#title").fill("조금 느리게 보낸 주말의 기록")
            page.locator("#body").fill("## 잠시 쉬어 가는 시간\n따뜻한 차 한 잔과 함께 오늘의 순간을 남겼어요.\n[[photo:1]]\n<script>이 문구는 실행되면 안 돼요</script>")
            page.locator("#instaTab").click()
            page.locator("#body").fill("조금 느리게, 조금 다정하게. 오늘의 순간을 남겨요. 🌿\n#일상기록 #주말")
            page.locator("#blogTab").click()
            assert "쉬어 가는" in page.locator("#body").input_value()
            page.locator("#save").click()
            expect(page.locator("#saveState")).to_have_text("저장 완료")
            assert page.locator("#body").input_value().startswith("제품을 제공받아")
            page.locator("#review").click()
            expect(page.locator("#qualityBox")).to_be_visible()
            page.locator('.step-button[data-step="3"]').click()
            expect(page.locator("#workflow")).to_have_attribute("data-stage","3")
            assert len(page.context.pages)==1
            page.locator('.step-button[data-step="2"]').click()
            expect(page.locator("#workflow")).to_have_attribute("data-stage","2")
            page.evaluate("document.fonts.ready")
            assert page.evaluate("document.fonts.check('15px NanumBareunHipi')")
            assert page.locator("#preview img").count()==1
            assert page.locator("#preview h2").inner_text()=="잠시 쉬어 가는 시간"
            assert page.locator("#preview script").count()==0
            page.screenshot(path=str(QA/"desktop-editor.png"),full_page=True)
            with page.expect_download() as download:
                page.locator("#export").click()
            downloaded=download.value
            content=Path(downloaded.path()).read_text(encoding="utf-8")
            assert "data:image/jpeg;base64," in content
            assert "&lt;script&gt;" in content
            page.reload()
            page.locator("#showDrafts").click()
            page.locator(".draft-row").first.click()
            expect(page.locator("#title")).to_have_value("조금 느리게 보낸 주말의 기록")
            expect(page.locator("#preview")).to_be_visible()
            assert page.locator(".photo").count()==1
            expect(page.locator("#tone")).to_have_value("짧고 위트 있게")
            expect(page.locator("#facts")).to_have_value("직접 따뜻한 차를 마시며 쉬었다.")
            expect(page.locator("#disclosure")).to_have_value("gifted")
            page.locator("#instaTab").click()
            assert "#일상기록" in page.locator("#body").input_value()
            page.locator("#publish").click()
            expect(page.locator("#modal")).to_be_visible()
            page.locator("#closeModal").click()
            page.locator("#blogTab").click()
            page.set_viewport_size({"width":390,"height":844})
            assert page.evaluate("document.documentElement.scrollWidth<=window.innerWidth")
            page.screenshot(path=str(QA/"mobile-editor.png"),full_page=True)
            page.on("dialog",lambda dialog:dialog.accept())
            page.locator("#prompt").fill("저장하기 전 복구할 테스트 메모")
            page.wait_for_timeout(1100)
            page.reload()
            expect(page.locator("#prompt")).to_have_value("저장하기 전 복구할 테스트 메모")
            page.locator("#save").click()
            expect(page.locator("#saveState")).to_have_text("저장 완료")
            page.locator("#publish").click()
            expect(page.locator("#modalTitle")).to_have_text("네이버 전달 · 코드로 직접 옮기기")
            expect(page.locator('input[aria-label="일회용 전달 코드"]')).to_have_value(__import__("re").compile(r"^[A-Za-z0-9_-]{32}$"))
            page.locator("#closeModal").click()
            assert len(page.context.pages)==1
            assert not errors,errors
            browser.close()
        print("Browser checks passed: upload, edit, channel switch, preview, XSS escaping, save/reopen, HTML download, settings, live workflow navigation and mobile overflow.")
    finally:
        process.terminate()
        process.wait(timeout=10)
