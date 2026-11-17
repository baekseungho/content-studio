"""처음 한 번 연결 후 앱 버튼만으로 글·사진·서식을 전달하는 전체 로컬 검증."""
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
from PIL import Image
from playwright.sync_api import sync_playwright,expect
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
sys.path.insert(0,str(Path(__file__).resolve().parent))
from test_extension import FIXTURE
ROOT=Path(__file__).resolve().parents[1]
FONT_TOOLBAR="""<button class="se-font-family-toolbar-button" data-name="font-family" onclick="document.querySelector('#fonts').hidden=false">서체 변경</button>
<div id="fonts" hidden><button role="option" data-value="nanumbareunhipi" onclick="document.querySelector('#font-style').textContent='.se-section-text{font-family:NanumBareunHipi}';this.parentElement.hidden=true">바른히피 서체 적용</button></div>
<button class="se-font-size-code-toolbar-button" data-name="font-size" onclick="document.querySelector('#sizes').hidden=false">15글자 크기 변경</button>
<div id="sizes" hidden><button role="option" data-value="fs15" onclick="document.querySelector('#size-style').textContent='.se-section-text{font-size:15px}';this.parentElement.hidden=true">15글자 크기</button></div>
<button class="se-property-toolbar-drop-down-button se-align-left-toolbar-button" data-name="align-drop-down-with-justify" onclick="document.querySelector('#alignment').hidden=false">정렬정렬 열기</button>
<div id="alignment" hidden><button class="se-toolbar-option-align-center-button" data-name="align-drop-down-with-justify" data-value="center" onclick="document.querySelector('#align-style').textContent='.se-section-text{text-align:center}';this.parentElement.hidden=true">가운데 정렬 선택</button></div>
<style id="font-style"></style><style id="size-style"></style><style id="align-style"></style>"""
with tempfile.TemporaryDirectory(prefix="easy-extension-") as temp:
 env={**os.environ,"PORT":"8878","STUDIO_DATA_DIR":str(Path(temp)/"data"),"OPENAI_API_KEY":"","NAVER_BLOG_ID":"test_fixture"}
 process=subprocess.Popen([sys.executable,str(ROOT/"app.py")],cwd=ROOT,env=env,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
 base="http://127.0.0.1:8878"
 try:
  for _ in range(60):
   try:
    with urllib.request.urlopen(base) as r:html=r.read().decode("utf-8-sig")
    break
   except Exception:time.sleep(.2)
  else:raise RuntimeError("server not ready")
  token=re.search('name="studio-token" content="([^"]+)"',html)[1]
  def post(path,body):
   req=urllib.request.Request(base+path,data=json.dumps(body).encode(),headers={"Content-Type":"application/json","X-Studio-Token":token})
   with urllib.request.urlopen(req) as r:return json.load(r)
  image=io.BytesIO();Image.new("RGB",(8,8),"green").save(image,"PNG")
  mid=post("/api/upload",{"data":base64.b64encode(image.getvalue()).decode()})["id"]
  post("/api/drafts",{"title":"쉬운 글쓰기 테스트","blog":"도입 이야기\n\n[[photo:1]]\n\n사진 뒤 이야기","instagram":"기록","images":[mid],"template":"reference"})
  with sync_playwright() as p:
   ext=str(ROOT/"chrome-extension")
   context=p.chromium.launch_persistent_context(str(Path(temp)/"browser"),channel="chromium",headless=True,
       args=["--disable-extensions-except="+ext,"--load-extension="+ext])
   try:
    # 이 URL 요청은 전부 로컬 HTML로 대체하며 실제 네이버에 접속하지 않는다.
    context.route("https://blog.naver.com/**",lambda route:route.fulfill(status=200,content_type="text/html; charset=utf-8",body=FONT_TOOLBAR+FIXTURE))
    worker=context.service_workers[0] if context.service_workers else context.wait_for_event("serviceworker")
    ext_id=worker.url.split("/")[2]
    # Extension-created first navigations escape Playwright routing; start blank and let the test navigate.
    worker.evaluate("""()=>{
     const create=chrome.tabs.create.bind(chrome.tabs);
     chrome.tabs.create=async props=>{
      const tab=await create({...props,url:'about:blank'});
      for(let i=0;i<200;i++){
       const state=await chrome.storage.session.get('fixtureReady');
       if(state.fixtureReady===tab.id)return chrome.tabs.get(tab.id);
       await new Promise(resolve=>setTimeout(resolve,50));
      }
      throw Error('fixture navigation timeout');
     };
    }""")
    setup=context.new_page();setup.goto("chrome-extension://"+ext_id+"/popup.html")
    setup.evaluate("base=>chrome.storage.local.set({pairedBase:base})",base)
    page=context.new_page();page.goto(base+"/#extension="+ext_id)
    expect(page.locator("#title")).to_have_value("쉬운 글쓰기 테스트",timeout=15000)
    assert page.evaluate("localStorage.getItem('dajeong-extension')") == ext_id
    with context.expect_page() as opened:
     page.locator("#publish").click()
    naver=opened.value
    naver.goto("https://blog.naver.com/test_fixture?Redirect=Write&")
    worker.evaluate("async()=>{const [tab]=await chrome.tabs.query({active:true});await chrome.storage.session.set({fixtureReady:tab.id});}")
    expect(page.locator("#publish")).to_be_enabled(timeout=60000)
    saved_diagnostic=json.loads((Path(temp)/"data"/"naver-extension-diagnostics.json").read_text(encoding="utf-8"))
    assert saved_diagnostic["version"]=="1.5.3" and saved_diagnostic["formatting"]["verified"]
    assert "report_token" not in saved_diagnostic
    print("First input and local diagnostic recording verified",flush=True)
    expect(page.locator("#jobProgress")).to_contain_text("적용을 확인했어요",timeout=1000)
    expect(page.locator("#workflow")).to_have_attribute("data-stage","3")
    expect(page.locator("#workflow")).to_have_attribute("data-state","ready")
    expect(page.locator("#workflowHint")).to_contain_text("네이버로 옮겼어요")
    expect(naver.locator("img.se-image-resource")).to_have_count(1)
    assert "도입 이야기" in naver.locator(".se-section-text").first.inner_text()
    assert "사진 뒤 이야기" in naver.locator(".se-section-text").last.inner_text()
    assert naver.locator(".se-section-text").first.evaluate("el=>getComputedStyle(el).textAlign")=="center"
    assert "bareunhipi" in naver.locator(".se-section-text").first.evaluate("el=>getComputedStyle(el).fontFamily").lower()
    assert page.locator("#modal").is_visible() is False
    page.locator("#instaTab").click()
    expect(page.locator("#workflow")).to_have_attribute("data-stage","2")
    expect(page.locator("#workflow")).to_have_attribute("data-state","")
    expect(page.locator("#lastStepLabel")).to_have_text("인스타에 올리기")
    expect(page.locator("#naverDiagnostic")).not_to_be_visible()
    page.locator("#blogTab").click()
    expect(page.locator("#workflow")).to_have_attribute("data-stage","2")
    # A second click must report the completed-draft reason, never silently open an empty tab.
    page.locator("#publish").click()
    expect(page.locator("#jobProgress")).to_contain_text("같은 글 다시 넣기")
    expect(page.locator("#naverDiagnostic")).to_contain_text("전달 준비 · 앱 검사")
    expect(page.get_by_role("button",name="진단 결과 복사")).to_be_visible()
    page.locator("#naverTestControls > summary").click()
    page.locator("#naverRepeat").check()
    def auto_attempt():
     with context.expect_page() as new_tab:page.locator("#publish").click()
     target=new_tab.value;target.goto("https://blog.naver.com/test_fixture?Redirect=Write&")
     worker.evaluate("async()=>{const [tab]=await chrome.tabs.query({active:true});await chrome.storage.session.set({fixtureReady:tab.id});}")
     expect(page.locator("#publish")).to_be_enabled(timeout=60000)
     return target
    limited=auto_attempt()
    expect(page.locator("#jobProgress")).to_contain_text("1분")
    expect(page.locator("#naverDiagnostic")).to_contain_text("초안 받기")
    expect(limited.locator("img.se-image-resource")).to_have_count(0)
    def age_test_attempts():
     # Only the isolated temporary test data is changed; production guard settings remain untouched.
     guard_file=Path(temp)/"data"/"naver-guard.json"
     state=json.loads(guard_file.read_text(encoding="utf-8"))
     state["attempts"]=[value-61 for value in state["attempts"]]
     guard_file.write_text(json.dumps(state),encoding="utf-8")
    age_test_attempts()
    second=auto_attempt()
    expect(page.locator("#jobProgress")).to_contain_text("적용을 확인했어요")
    expect(second.locator("img.se-image-resource")).to_have_count(1)
    expect(page.locator("#naverDiagnostic")).to_contain_text("정렬: 적용 확인")
    age_test_attempts()
    page.locator("#naverManual").click()
    expect(page.locator("#modal")).to_be_visible()
    code=page.locator('input[aria-label="일회용 전달 코드"]').input_value()
    manual=context.new_page();manual.goto("https://blog.naver.com/test_fixture?manual=1")
    manual_id=worker.evaluate("async()=>{const tabs=await chrome.tabs.query({url:'https://blog.naver.com/*'});const tab=tabs.find(tab=>tab.url.includes('manual=1'));await chrome.tabs.update(tab.id,{active:true});return tab.id;}")
    setup.evaluate("args=>{document.getElementById('base').value=args.base;document.getElementById('code').value=args.code;document.getElementById('fill').click();}",{"base":base,"code":code})
    expect(setup.locator("#fill")).to_be_enabled(timeout=60000)
    expect(setup.locator("#status")).to_contain_text("적용을 확인했어요")
    expect(setup.locator("#code")).to_have_value("")
    expect(manual.locator("img.se-image-resource")).to_have_count(1)
    before=manual.locator(".se-section-text").all_inner_texts()
    manual.locator("#align-style").evaluate("el=>el.textContent='.se-section-text{text-align:left}'")
    result=worker.evaluate("id=>formatOnly(id)",manual_id)
    assert result["ok"],result
    assert manual.locator(".se-section-text").all_inner_texts()==before
    expect(manual.locator("img.se-image-resource")).to_have_count(1)
    assert manual.locator(".se-text-paragraph").last.evaluate("el=>getComputedStyle(el).textAlign")=="center"
    page.locator("#closeModal").click()
    from test_tistory import FIXTURE as TISTORY_FIXTURE
    context.route("https://my-blog.tistory.com/**",lambda route:route.fulfill(status=200,content_type="text/html; charset=utf-8",body=TISTORY_FIXTURE))
    context.route("https://media.test/**",lambda route:route.fulfill(content_type="image/png",body=image.getvalue()))
    page.locator("#tistoryTab").click()
    page.locator("#tistorySettings details").evaluate("el=>el.open=true")
    page.locator("#tistoryUrl").fill("https://my-blog.tistory.com")
    with context.expect_page() as opened_tistory:
     page.locator("#publish").click()
    tistory=opened_tistory.value
    tistory.goto("https://my-blog.tistory.com/manage/newpost/")
    worker.evaluate("async()=>{const tabs=await chrome.tabs.query({url:'https://my-blog.tistory.com/*'});await chrome.storage.session.set({fixtureReady:tabs[0].id});}")
    expect(page.locator("#publish")).to_be_enabled(timeout=60000)
    expect(page.locator("#naverDiagnostic")).to_contain_text("티스토리로 잘 옮겼어요")
    page.locator("#tistoryUrl").fill("")
    page.locator("#detectTistory").click()
    expect(page.locator("#tistoryUrl")).to_have_value("https://my-blog.tistory.com")
    expect(page.locator("#tistoryDetected")).to_have_text("https://my-blog.tistory.com")
    expect(tistory.locator("#content img")).to_have_count(1)
    expect(tistory.locator("#post-title-inp")).not_to_have_value("")
    print("Tistory flow passed: app tab, isolated handoff, extension, text/photo insertion and diagnostic.",flush=True)
    qa=ROOT/"data"/"qa";qa.mkdir(exist_ok=True)
    naver.screenshot(path=str(qa/"native-format-fixture.png"),full_page=True)
    page.screenshot(path=str(qa/"easy-app.png"),full_page=True)
    print("Flow passed: first input, visible repeat rejection, visible 60-second cooldown, confirmed repeat, manual code continuation and format-only repair without duplicate photos. No real Naver navigation or publishing.")
   finally:
    for opened_page in context.pages:
     try:opened_page.evaluate("window.onbeforeunload=null;window.addEventListener('beforeunload',event=>event.stopImmediatePropagation(),true)")
     except Exception:pass
    context.close()
 finally:
  process.terminate();process.wait(timeout=10)
