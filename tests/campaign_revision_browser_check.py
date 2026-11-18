import os,subprocess,sys,tempfile,time,urllib.request
from pathlib import Path
from playwright.sync_api import sync_playwright,expect
root=Path(__file__).resolve().parents[1]
with tempfile.TemporaryDirectory() as folder:
 process=subprocess.Popen([sys.executable,str(root/'app.py')],cwd=root,env={**os.environ,'PORT':'8882','STUDIO_DATA_DIR':folder,'OPENAI_API_KEY':'','NAVER_BLOG_ID':'fixture'},stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
 try:
  for _ in range(60):
   try:urllib.request.urlopen('http://127.0.0.1:8882/api/status',timeout=1).close();break
   except Exception:time.sleep(.2)
  with sync_playwright() as p:
   browser=p.chromium.launch(headless=True);page=browser.new_page(viewport={'width':1440,'height':1100});page.on('dialog',lambda d:d.accept());errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
   page.goto('http://127.0.0.1:8882');page.locator('#campaignMode').click();page.locator('#missionDetails').evaluate('el=>el.open=true');page.locator('#campaign_min_chars').fill('100');page.locator('#campaign_max_chars').fill('50');expect(page.locator('#lengthError')).to_be_visible()
   page.locator('#campaign_min_chars').fill('0');page.locator('#campaign_max_chars').fill('100');expect(page.locator('#lengthError')).to_be_hidden()
   page.locator('#campaign_count_spaces').check();page.locator('#disclosure').select_option('experience');page.locator('#title_keywords').fill('필수키워드');page.locator('#manualStart').click();page.locator('#title').fill('카페 후기');page.locator('#body').fill('본문 내용')
   page.locator('#publish').click();expect(page.locator('#title_keywords')).to_have_attribute('aria-invalid','true');expect(page.locator('#issue-for-title_keywords')).to_contain_text('제목에 이 키워드가 없어요')
   expect(page.locator('#title_keywords')).to_be_focused();expect(page.locator('#publish')).to_be_enabled()
   page.locator('#qualityBox').get_by_role('button',name='제목 수정',exact=True).click();expect(page.locator('#title')).to_be_focused()
   page.locator('#title').fill('필수키워드 카페 후기');expect(page.locator('#title_keywords')).not_to_have_attribute('aria-invalid','true',timeout=5000)
   page.locator('#campaignPanel').evaluate('el=>el.open=true');page.locator('#campaign_max_chars').fill('5');expect(page.locator('#campaign_max_chars')).to_have_attribute('aria-invalid','true',timeout=5000)
   expect(page.locator('#issue-for-campaign_max_chars')).to_contain_text('최대 5자')
   for width in (320,390,768):
    page.set_viewport_size({'width':width,'height':1000});assert page.evaluate('document.documentElement.scrollWidth<=innerWidth'),width
   page.set_viewport_size({'width':1440,'height':1100})
   page.locator('#campaign_max_chars').fill('100');expect(page.locator('#campaign_max_chars')).not_to_have_attribute('aria-invalid','true',timeout=5000)
   page.locator('#save').click();expect(page.locator('#saveState')).to_have_text('저장 완료');page.locator('#newDraft').click();page.locator('#showDrafts').click();page.locator('.draft-row').first.click();expect(page.locator('#modal')).to_be_hidden();expect(page.locator('#campaign_max_chars')).to_have_value('100');expect(page.locator('#campaign_count_spaces')).to_be_checked()
   for width in (320,390,768,1440):
    page.set_viewport_size({'width':width,'height':1000});assert page.evaluate('document.documentElement.scrollWidth<=innerWidth'),width
   page.locator('#campaignPanel').evaluate('el=>el.open=true');page.screenshot(path=str(root/'data/qa/campaign-length-errors.png'),full_page=True)
   assert not errors,errors;browser.close();print('Campaign revision browser passed: ranges, reasons, field highlight/focus, edit links, revalidation, persistence and mobile')
 finally:process.terminate();process.wait(timeout=10)
