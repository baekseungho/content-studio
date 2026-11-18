import os,subprocess,sys,tempfile,time,urllib.request
from pathlib import Path
from playwright.sync_api import sync_playwright,expect
r=Path(__file__).resolve().parents[1]
with tempfile.TemporaryDirectory() as folder:
 process=subprocess.Popen([sys.executable,str(r/'app.py')],cwd=r,env={**os.environ,'PORT':'8884','STUDIO_DATA_DIR':folder,'OPENAI_API_KEY':''},stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
 try:
  for _ in range(60):
   try:urllib.request.urlopen('http://127.0.0.1:8884/api/status',timeout=1).close();break
   except Exception:time.sleep(.2)
  with sync_playwright() as p:
   browser=p.chromium.launch(headless=True);page=browser.new_page(viewport={'width':1440,'height':1050});page.on('dialog',lambda d:d.accept());errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
   page.goto('http://127.0.0.1:8884');page.wait_for_function('Object.keys(status).length>0')
   expect(page.locator('#moreOptions')).not_to_have_attribute('open','');expect(page.locator('#writingOptions')).not_to_have_attribute('open','');expect(page.locator('textarea:visible')).to_have_count(1)
   assert '이용료' not in page.locator('body').inner_text() and '이용 내역' not in page.locator('body').inner_text();assert page.locator('#generationInfo').count()==0
   page.locator('#prompt').fill('오늘의 카페 이야기');page.locator('#moreOptions>summary').click();page.locator('#facts').fill('커피가 고소했어요.');page.locator('#hashtags').fill('#Cafe')
   expect(page.locator('#contentOptionsSummary')).to_contain_text('추가 메모')
   page.locator('#writingOptions>summary').click();page.locator('#language').select_option('en');expect(page.locator('#writingOptionsSummary')).to_contain_text('English')
   page.locator('#campaignMode').click();expect(page.locator('#campaignDisclosureSlot #disclosure')).to_be_visible();expect(page.locator('#missionDetails')).not_to_have_attribute('open','');page.locator('#disclosure').select_option('experience');page.locator('#campaign_brand').fill('Sample cafe');page.locator('#missionDetails>summary').click();expect(page.locator('#missionDetails #hashtags')).to_have_value('#Cafe')
   page.locator('#campaign_max_chars').fill('1000');page.locator('#personalMode').click();expect(page.locator('#tagHome #hashtags')).to_have_value('#Cafe');expect(page.locator('#disclosureHome #disclosure')).to_have_value('experience')
   page.locator('#manualStart').click();page.locator('#title').fill('A coffee break');page.locator('#body').fill('A little coffee break.');page.locator('#save').click();expect(page.locator('#saveState')).to_have_text('저장 완료')
   page.evaluate('status.ai=true');page.route('**/api/generate',lambda route:route.fulfill(json={'job':'organized'}));page.route('**/api/jobs/organized',lambda route:route.fulfill(json={'state':'done','result':{'title':'A coffee break','blog':'A little coffee break.','generation':{'model':'hidden-model-name','input_tokens':123,'output_tokens':45,'web_search_calls':0}}}))
   page.locator('#generate').click();assert '이용료' not in page.locator('#modal').inner_text();page.locator('#startSelectedGeneration').click();expect(page.locator('#writingProgress')).to_have_attribute('data-state','done');assert 'hidden-model-name' not in page.locator('body').inner_text()
   page.locator('#threadsTab').click();page.locator('#closeModal').click();expect(page.locator('#threadsOptions')).not_to_have_attribute('open','');page.locator('#threadsOptions>summary').click();expect(page.locator('#threadsTone')).to_be_visible()
   page.locator('#blogTab').click();page.locator('#campaignMode').click();page.locator('#missionDetails').evaluate('el=>el.open=true');page.locator('#title_keywords').fill('missing-keyword');page.locator('#review').click();expect(page.locator('#qualityBox')).to_contain_text('missing-keyword');expect(page.locator('#qualityBox').get_by_role('button',name='조건 수정').first).to_be_visible()
   for theme in ('light','dark'):
    page.evaluate("theme=>{document.documentElement.dataset.theme=theme;document.documentElement.style.colorScheme=theme}",theme)
    for width in (320,390,768,1440):
     page.set_viewport_size({'width':width,'height':1050});assert page.evaluate('document.documentElement.scrollWidth<=innerWidth'),(theme,width)
    page.locator('#campaignPanel').evaluate('el=>el.open=false');page.locator('#writingOptions').evaluate('el=>el.open=false');page.locator('#moreOptions').evaluate('el=>el.open=false');page.evaluate('window.scrollTo(0,0)');page.screenshot(path=str(r/('data/qa/organized-ui-'+theme+'.png')),full_page=True)
   assert not errors,errors;browser.close();print('Organized UI passed: first-use simplicity, grouped controls, state preservation, no fee/usage surfaces, generation, actionable errors, themes and mobile')
 finally:process.terminate();process.wait(timeout=10)
