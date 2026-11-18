import os,subprocess,sys,tempfile,time,urllib.request
from pathlib import Path
from playwright.sync_api import sync_playwright,expect
r=Path(__file__).resolve().parents[1]
with tempfile.TemporaryDirectory() as folder:
 process=subprocess.Popen([sys.executable,str(r/'app.py')],cwd=r,env={**os.environ,'PORT':'8883','STUDIO_DATA_DIR':folder,'OPENAI_API_KEY':''},stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
 try:
  for _ in range(60):
   try:urllib.request.urlopen('http://127.0.0.1:8883/api/status',timeout=1).close();break
   except Exception:time.sleep(.2)
  with sync_playwright() as p:
   browser=p.chromium.launch(headless=True);page=browser.new_page(viewport={'width':1440,'height':1100});page.on('dialog',lambda d:d.accept());errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
   calls=[];page.route('**/api/generate',lambda route:(calls.append(True),route.abort()))
   page.goto('http://127.0.0.1:8883');page.locator('#writingOptions').evaluate('el=>el.open=true');page.locator('#layoutPanel>summary').click();expect(page.locator('[data-layout=manual]')).to_have_attribute('aria-pressed','true');expect(page.locator('#layoutApply')).to_be_disabled()
   page.locator('#manualStart').click();page.locator('#title').fill('줄바꿈 테스트')
   original='오늘의 작은 이야기를 사진 사이에 편안하게 남겨 보려고 해요. 읽는 사람이 잠깐 숨을 고를 수 있도록 한 줄의 길이와 문단의 호흡을 나누어 볼 거예요. 긴 문장이 조금 더 부드럽게 보이면 좋겠어요.'
   page.locator('#body').fill(original);page.locator('[data-layout=notes]').click();page.locator('#layoutApply').click();expect(page.locator('#layoutStatus')).to_contain_text('적용했어요');expect(page.locator('#layoutApply')).to_be_enabled()
   compact=page.locator('#body').input_value();assert '\n' in compact and compact.split()==original.split()
   page.locator('[data-layout=review]').click();page.locator('#layoutApply').click();expect(page.locator('#layoutApply')).to_be_enabled();expect(page.locator('#body')).not_to_have_value(compact)
   page.locator('#layoutUndo').click();expect(page.locator('#body')).to_have_value(original)
   page.locator('[data-layout=notes]').click();page.locator('#layoutApply').click();expect(page.locator('#layoutApply')).to_be_enabled();page.locator('#body').fill('직접 고친 문장을 보호해 주세요.');expect(page.locator('#layoutUndo')).to_be_disabled()
   page.locator('[data-layout=comfort]').click();page.locator('#layoutApply').click();expect(page.locator('#layoutApply')).to_be_enabled();page.locator('#save').click();expect(page.locator('#saveState')).to_have_text('저장 완료')
   page.locator('#newDraft').click();page.locator('#showDrafts').click();page.locator('.draft-row').first.click();expect(page.locator('#modal')).to_be_hidden();page.locator('#writingOptions').evaluate('el=>el.open=true');page.locator('#layoutPanel').evaluate('el=>el.open=true');expect(page.locator('[data-layout=comfort]')).to_have_attribute('aria-pressed','true')
   assert page.evaluate('draft.layout_bases.naver')=='직접 고친 문장을 보호해 주세요.'
   page.locator('#tistoryTab').click();expect(page.locator('[data-layout=manual]')).to_have_attribute('aria-pressed','true');page.locator('[data-layout=review]').click();page.locator('#blogTab').click();expect(page.locator('[data-layout=comfort]')).to_have_attribute('aria-pressed','true')
   for width in (320,390,768,1440):
    page.set_viewport_size({'width':width,'height':1000});assert page.evaluate('document.documentElement.scrollWidth<=innerWidth'),width
   page.locator('#layoutPanel').scroll_into_view_if_needed();page.screenshot(path=str(r/'data/qa/blog-layout-controls.png'),full_page=True)
   assert not calls and not errors,(calls,errors);browser.close();print('Layout browser passed: presets, apply, reversible reflow, manual edit safety, save/reopen, platform isolation, zero AI calls and mobile')
 finally:process.terminate();process.wait(timeout=10)
