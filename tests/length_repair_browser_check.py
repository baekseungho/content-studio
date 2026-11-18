import os,subprocess,sys,tempfile,time,urllib.request
from pathlib import Path
from playwright.sync_api import sync_playwright,expect
r=Path(__file__).resolve().parents[1]
with tempfile.TemporaryDirectory() as folder:
 process=subprocess.Popen([sys.executable,str(r/'app.py')],cwd=r,env={**os.environ,'PORT':'8885','STUDIO_DATA_DIR':folder,'OPENAI_API_KEY':''},stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
 try:
  for _ in range(60):
   try:urllib.request.urlopen('http://127.0.0.1:8885/api/status',timeout=1).close();break
   except Exception:time.sleep(.2)
  with sync_playwright() as p:
   browser=p.chromium.launch(headless=True);page=browser.new_page(viewport={'width':1440,'height':1050});errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
   page.goto('http://127.0.0.1:8885');page.locator('#moreOptions>summary').click();page.locator('#placePanel>summary').click()
   for width in (320,390,768,1440):
    page.set_viewport_size({'width':width,'height':1050})
    box=page.locator('.place-panel .research').bounding_box();check=page.locator('#research').bounding_box();text=page.locator('.place-panel .research>span').first.bounding_box()
    assert 14<=check['width']<=18 and check['height']<=18,(width,check)
    assert text['width']>=90 and box['height']<300,(width,box,text)
    assert page.evaluate('document.documentElement.scrollWidth<=innerWidth')
   page.locator('#research').check();page.locator('#research').uncheck();page.locator('#placePanel').screenshot(path=str(r/'data/qa/research-checkbox-fixed.png'))
   page.locator('#campaignMode').click();page.locator('#missionDetails').evaluate('el=>el.open=true');page.locator('#campaign_min_chars').fill('2000');page.locator('#campaign_count_spaces').check();page.locator('#disclosure').select_option('experience');page.locator('#prompt').fill('메모에 적은 메뉴와 맛을 사용해 주세요.')
   for field in ('campaign_min_chars','campaign_max_chars'):
    expect(page.locator('#'+field)).to_have_attribute('max','5000')
    page.locator('#'+field).fill('5001');page.locator('#generate').click()
    expect(page.locator('#lengthError')).to_contain_text('5,000');expect(page.locator('#modal')).not_to_be_visible()
    page.locator('#'+field).fill('2000' if field=='campaign_min_chars' else '0')
   page.locator('#manualStart').click();page.locator('#title').fill('기존 제목');page.locator('#body').fill('현재 초안의 실제 내용을 유지해 주세요.');page.locator('#review').click();expect(page.get_by_role('button',name='이 초안에서 분량 보완')).to_be_visible()
   calls=[]
   def repair(route):
    calls.append(route.request.post_data_json);route.fulfill(json={'job':'length-test'})
   page.route('**/api/blog/expand',repair)
   page.route('**/api/jobs/length-test',lambda route:route.fulfill(json={'state':'done','result':{'title':'기존 제목','blog':'기존 경험을 보완한 초안입니다.','needs_more_notes':True,'checks':[{'level':'error','field':'campaign_min_chars','target':'body','message':'현재 40자 / 최소 2000자'}]}}))
   page.get_by_role('button',name='이 초안에서 분량 보완').click();expect(page.locator('#generate')).to_be_enabled();expect(page.locator('#toast')).to_contain_text('분량 조건이 남아')
   assert len(calls)==1 and calls[0]['platforms']==['naver'];assert '현재 초안' in calls[0]['seed']['body']
   expect(page.locator('#qualityBox')).to_contain_text('최소 2000자');assert page.evaluate('draft.instagram')==''
   page.get_by_role('button',name='경험 메모 추가',exact=True).click();expect(page.locator('#facts')).to_be_focused()
   assert not errors,errors;browser.close();print('Length/UI checks passed: bounded checkbox layout, 2000-character requirement, current-draft repair, partial feedback, memo focus and no other-platform changes')
 finally:process.terminate();process.wait(timeout=10)
