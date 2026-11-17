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
            assert page.locator("#threadsCommunity").is_checked()
            expect(page).to_have_title("Mellow Studio · 나다운 이야기를 만드는 곳")
            expect(page.locator(".insta-dot svg")).to_have_count(1)
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
            page.evaluate("()=>{draft.sources=[{title:'테스트 참고 자료',url:'https://example.com/reference'}];renderTab();}")
            expect(page.locator("#sourceDetails")).not_to_be_visible()
            expect(page.locator("#sourceBox a")).to_have_count(0)
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
            expect(page.locator("#modal")).to_be_hidden()
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
            page.locator("#tistoryTab").click()
            expect(page.locator("#tistorySettings")).to_be_visible()
            expect(page.locator("#publish")).to_have_text("티스토리로 옮기기 ↗")
            expect(page.locator("#preview")).to_be_visible()
            page.evaluate("document.fonts.ready")
            assert "Nanum Myeongjo" in page.locator("#preview").evaluate("el=>getComputedStyle(el).fontFamily")
            page.locator("#tistorySettings details").evaluate("el=>el.open=true")
            page.locator("#tistoryUrl").fill("https://my-blog.tistory.com")
            page.locator("#blogTab").click()
            expect(page.locator("#tistorySettings")).to_be_hidden()
            page.locator("#instaTab").click()
            expect(page.locator(".insta-photo-strip img")).to_have_count(1)
            assert page.locator(".insta-photo-strip img").bounding_box()["height"]<=130
            expect(page.locator("#preview")).to_contain_text("조금 느리게")
            for width in (320,768,1440):
                page.set_viewport_size({"width":width,"height":1000})
                assert page.evaluate("document.documentElement.scrollWidth<=innerWidth")
            page.screenshot(path=str(QA/"instagram-compact-preview.png"),full_page=True)
            page.locator("#blogTab").click()
            # Exercise real Generate click + polling, without contacting AI services.
            import json
            page.evaluate("()=>{status.ai=true;}")
            page.route("**/api/generate",lambda route:route.fulfill(json={"job":"visual-test"}))
            events=iter([{"state":"running","stage":2,"message":"이야기를 쓰고 있어요."},
                         {"state":"running","stage":3,"message":"말투를 다듬고 있어요."},
                         {"state":"running","stage":4,"message":"마지막 확인 중이에요."},
                         {"state":"done","result":{"title":"완성된 제목","blog":"완성된 이야기","instagram":"완성된 캡션"}}])
            page.route("**/api/jobs/visual-test",lambda route:route.fulfill(json=next(events)))
            page.locator("#generate").click()
            page.locator("#startSelectedGeneration").click()
            expect(page.locator("#writingProgress")).to_have_attribute("data-state","running")
            expect(page.locator("#generate")).to_be_disabled()
            expect(page.locator(".writing-stages .is-active")).to_have_text("이야기 쓰기",timeout=5000)
            page.screenshot(path=str(QA/"writing-progress.png"),full_page=True)
            for width in (320,768,1440):
                page.set_viewport_size({"width":width,"height":1000})
                assert page.evaluate("document.documentElement.scrollWidth<=innerWidth"),width
            expect(page.locator("#writingProgress")).to_have_attribute("data-state","done",timeout=15000)
            expect(page.locator("#generate")).to_be_enabled()
            expect(page.locator("#resultCard")).to_have_attribute("aria-busy","false")
            expect(page.locator("#preview")).to_contain_text("완성된 이야기")
            page.unroute("**/api/jobs/visual-test")
            page.route("**/api/jobs/visual-test",lambda route:route.fulfill(json={"state":"failed","error":"연결을 확인해 주세요."}))
            page.locator("#generate").click()
            page.locator("#startSelectedGeneration").click()
            expect(page.locator("#writingProgress")).to_have_attribute("data-state","error",timeout=5000)
            expect(page.locator("#writingMessage")).to_have_text("연결을 확인해 주세요.")
            expect(page.locator("#preview")).to_contain_text("완성된 이야기")
            expect(page.locator("#generate")).to_be_enabled()
            page.locator("#newDraft").click()
            expect(page.locator("#writingProgress")).to_be_hidden()
            # Midpoint: photo removal, save races, immediate recovery and offline errors.
            page.locator("#photos").set_input_files([{"name":str(i)+".png","mimeType":"image/png","buffer":image.getvalue()} for i in range(3)])
            expect(page.locator(".photo")).to_have_count(3)
            page.locator("#manualStart").click()
            page.locator("#title").fill("중간 점검 초안")
            page.locator("#body").fill("첫 사진\n[[photo:1]]\n\n둘째 사진\n[[photo:2]]\n\n셋째 사진\n[[photo:3]]")
            original_ids=page.evaluate("draft.images.slice()")
            page.locator("#previewToggle").click()
            page.get_by_role("button",name="사진 2 삭제",exact=True).click()
            expect(page.locator("#preview img")).to_have_count(2)
            assert page.evaluate("draft.images")==[original_ids[0],original_ids[2]]
            assert "[[photo:3]]" not in page.evaluate("draft.blog")
            assert page.locator("#preview img").last.get_attribute("src").endswith(original_ids[2]+".jpg")
            expect(page.locator("#photoChangeHint")).to_be_visible()
            page.locator("#photos").set_input_files({"name":"added.png","mimeType":"image/png","buffer":image.getvalue()})
            expect(page.locator("#preview img")).to_have_count(3)
            pending=[]
            page.route("**/api/drafts",lambda route:pending.append(route) if route.request.method=="POST" else route.continue_())
            page.locator("#save").click()
            expect(page.locator("#body")).to_be_disabled()
            expect(page.locator("#instaTab")).to_be_disabled()
            expect(page.locator("#save")).to_be_disabled()
            result=page.evaluate("async()=>{try{await saveDraft();return 'unexpected';}catch(error){return error.message;}}")
            assert "진행 중" in result and len(pending)==1
            request=pending.pop();response=request.fetch();request.fulfill(response=response);page.unroute("**/api/drafts")
            expect(page.locator("#saveState")).to_have_text("저장 완료")
            page.locator("#previewToggle").click()
            page.locator("#body").fill("새로고침 직전의 마지막 문장")
            page.evaluate("()=>window.dispatchEvent(new Event('beforeunload',{cancelable:true}))")
            assert page.evaluate("JSON.parse(localStorage.getItem('dajeong-recovery')).draft.blog")=="새로고침 직전의 마지막 문장"
            page.route("**/api/drafts",lambda route:route.abort("failed"))
            page.locator("#save").click()
            expect(page.locator("#toast")).to_contain_text("앱과 연결이 끊겼어요")
            expect(page.locator("#body")).to_have_value("새로고침 직전의 마지막 문장")
            expect(page.locator("#body")).to_be_enabled()
            assert page.evaluate("dirty") is True
            assert page.evaluate("JSON.parse(localStorage.getItem('dajeong-recovery')).draft.blog")=="새로고침 직전의 마지막 문장"
            page.unroute("**/api/drafts")
            page.locator("#instaTab").click()
            page.locator("#publish").click()
            expect(page.locator("#jobProgress")).to_contain_text("인스타그램에 올릴 글을 먼저")
            page.locator("#blogTab").click()
            preflight=[]
            page.route("**/api/status",lambda route:preflight.append(route))
            page.locator("#publish").click()
            expect(page.locator("#instaTab")).to_be_disabled()
            expect(page.locator("#newDraft")).to_be_disabled()
            assert len(preflight)==1
            preflight.pop().fulfill(json={"ai":False,"naver":False,"instagram":False})
            expect(page.locator("#modal")).to_be_visible()
            expect(page.locator("#instaTab")).to_be_enabled()
            page.locator("#closeModal").click()
            # Threads is a separate draft field, and opening a composer never calls publishing APIs.
            original_blog=page.locator("#body").input_value()
            page.locator("#threadsTab").click()
            expect(page.locator("#threadsOptions")).to_be_visible()
            expect(page.locator("#title")).to_be_hidden()
            page.locator("#language").select_option("en")
            page.locator("#threadsTone").select_option("witty")
            post="A window seat, a good coffee, and absolutely no rush. That's the plan. 🤍"
            page.locator("#body").fill(post)
            expect(page.locator("#charCount")).to_contain_text("/ 500자")
            page.locator("#previewToggle").click()
            expect(page.locator("#preview")).to_contain_text(post)
            expect(page.locator("#preview script")).to_have_count(0)
            page.locator("#blogTab").click()
            assert page.locator("#body").input_value()==original_blog
            page.locator("#threadsTab").click()
            page.locator("#save").click()
            expect(page.locator("#saveState")).to_have_text("저장 완료")
            assert page.evaluate("draft.threads")==post
            page.locator("#review").click()
            expect(page.locator("#qualityBox")).not_to_contain_text("블로그 제목이 비어")
            page.locator("#threadsManual").click()
            expect(page.locator("#modalTitle")).to_have_text("Threads에서 이어 쓰기")
            from urllib.parse import urlparse,parse_qs
            link=page.locator("#threadsComposerLink").get_attribute("href")
            assert urlparse(link).netloc=="www.threads.com" and parse_qs(urlparse(link).query)["text"]==[post]
            assert len(page.context.pages)==1
            page.locator("#closeModal").click()
            page.route("**/api/status",lambda route:route.fulfill(json={"ai":True,"threads":False,"threads_details":{"media_ready":False}}))
            page.locator("#publish").click()
            expect(page.locator("#modalTitle")).to_have_text("Threads 연결")
            expect(page.locator("#modalBody")).to_contain_text("THREADS_USER_ID")
            page.locator("#closeModal").click()
            page.unroute("**/api/status")
            page.route("**/api/status",lambda route:route.fulfill(json={"ai":True,"threads":True,"threads_details":{"media_ready":True}}))
            thread_posts=[]
            page.route("**/api/publish/threads",lambda route:(thread_posts.append(route.request.post_data_json),route.fulfill(json={"job":"threads-publish-test"})))
            page.route("**/api/jobs/threads-publish-test",lambda route:route.fulfill(json={"state":"done","result":{"media_id":"threads-test","state":"published"}}))
            page.locator("#threadsPhotos").uncheck()
            page.locator("#publish").click()
            expect(page.locator("#workflow")).to_have_attribute("data-state","published",timeout=5000)
            assert thread_posts==[{"id":page.evaluate("draft.id"),"with_images":False,"confirm":True}]
            expect(page.locator("#jobProgress")).to_contain_text("Threads에 발행했어요")
            page.unroute("**/api/status")
            for width in (320,390,768,1440):
                page.set_viewport_size({"width":width,"height":1000})
                assert page.evaluate("document.documentElement.scrollWidth<=innerWidth"),width
            page.screenshot(path=str(QA/"threads-english-preview.png"),full_page=True)
            page.locator("#showDrafts").click()
            page.locator(".draft-row").first.click()
            expect(page.locator("#modal")).to_be_hidden()
            expect(page.locator("#language")).to_have_value("en")
            page.locator("#threadsTab").click()
            expect(page.locator("#preview")).to_contain_text(post)
            expect(page.locator("#threadsTone")).to_have_value("witty")
            # Campaign mode is editable, persistent, and checked before blog handoff.
            page.locator("#blogTab").click()
            page.locator("#language").select_option("ko")
            page.locator("#campaignMode").click()
            expect(page.locator("#campaignPanel")).to_be_visible()
            page.locator("#campaign_brand").fill("샘플 카페")
            page.locator("#campaign_benefit").fill("식사권")
            page.locator("#campaign_brief").fill("업체에서 받은 안내문")
            page.locator("#title_keywords").fill("성수카페")
            page.locator("#body_keywords").fill("성수카페")
            page.locator("#hashtags").fill("#성수카페 #성수맛집")
            page.locator("#disclosure").select_option("none")
            page.locator("#moreOptions").evaluate("element=>element.open=false")
            page.locator("#publish").click()
            expect(page.locator("#moreOptions")).to_have_attribute("open","")
            expect(page.locator("#disclosure")).to_be_focused()
            expect(page.locator("#disclosure")).to_have_attribute("aria-invalid","true")
            expect(page.locator("#toast")).to_contain_text("제품·식사/이용권")
            page.locator("#personalMode").click()
            expect(page.locator("#disclosure")).not_to_have_attribute("aria-invalid","true")
            expect(page.locator("#jobProgress")).to_be_hidden()
            page.locator("#campaignMode").click()
            expect(page.locator("#modal")).to_be_hidden()
            page.locator("#disclosure").select_option("experience")
            expect(page.locator("#disclosure")).not_to_have_attribute("aria-invalid","true")
            if not page.locator("#body").is_visible():page.locator("#previewToggle").click()
            page.locator("#title").fill("성수카페에서 잠깐 쉬어간 날")
            page.locator("#body").fill("성수카페 샘플 카페에서 고소한 라테를 마셨어요.")
            page.locator("#save").click()
            expect(page.locator("#saveState")).to_have_text("저장 완료")
            expect(page.locator("#campaignChecklist")).to_be_visible()
            expect(page.locator("#campaignChecklist .is-missing")).to_have_count(0)
            assert page.evaluate("draft.blog").endswith("#성수카페 #성수맛집")
            expect(page.locator("#copyTags")).to_be_visible()
            for width in (320,390,768,1440):
                page.set_viewport_size({"width":width,"height":1000})
                assert page.evaluate("document.documentElement.scrollWidth<=innerWidth"),width
            if page.locator("#previewToggle").inner_text()=="미리보기":page.locator("#previewToggle").click()
            page.evaluate("window.scrollTo(0,0)")
            page.screenshot(path=str(QA/"campaign-studio.png"),full_page=True)
            page.locator("#showDrafts").click();page.locator(".draft-row").first.click()
            expect(page.locator("#modal")).to_be_hidden()
            expect(page.locator("#campaignPanel")).to_be_visible()
            expect(page.locator("#campaign_brief")).to_have_value("업체에서 받은 안내문")
            page.locator(".mission-edit").click()
            page.locator("#title_keywords").fill("없는키워드")
            expect(page.locator("#campaignChecklist .is-missing")).to_have_count(1)
            page.locator("#threadsTab").click()
            page.locator("#threadsCommunity").check();page.locator("#threadsNetworking").check()
            expect(page.locator("#campaignChecklist")).to_be_hidden()
            page.locator("#save").click();expect(page.locator("#saveState")).to_have_text("저장 완료")
            assert page.evaluate("draft.threads_community && draft.threads_networking") is True
            page.locator("#showDrafts").click();page.locator(".draft-row").first.click()
            expect(page.locator("#modal")).to_be_hidden();page.locator("#threadsTab").click()
            expect(page.locator("#threadsCommunity")).to_be_checked()
            expect(page.locator("#threadsNetworking")).to_be_checked()
            assert not errors,errors
            browser.close()
        print("Browser checks passed: upload, edit, channel switch, preview, XSS escaping, save/reopen, HTML download, settings, live workflow navigation and mobile overflow.")
    finally:
        process.terminate()
        process.wait(timeout=10)
