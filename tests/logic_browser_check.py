"""Real multi-window saves and validation; isolated drafts, no real AI or SNS calls."""
import json,os,subprocess,sys,tempfile,time,urllib.request
from pathlib import Path
from playwright.sync_api import sync_playwright,expect
ROOT=Path(__file__).resolve().parents[1]
def fill_body(page,text):
 if page.evaluate('tab')!='blog':page.locator('#body').fill(text);return
 page.evaluate('text=>{const prior=BlockWorkspace.ensure();const doc=StoryBlocks.create(text,StoryBlocks.photos(prior),draft[titleKey()],prior.template,prior);BlockWorkspace.commit(doc);BlockWorkspace.refresh();}',text)
with tempfile.TemporaryDirectory(prefix='mellow-logic-') as folder:
 process=subprocess.Popen([sys.executable,str(ROOT/'app.py')],cwd=ROOT,env={**os.environ,'PORT':'8889','STUDIO_DATA_DIR':folder,'OPENAI_API_KEY':'','THREADS_ACCESS_TOKEN':''},stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
 try:
  for _ in range(60):
   try:urllib.request.urlopen('http://127.0.0.1:8889/api/status',timeout=1).close();break
   except Exception:time.sleep(.2)
  with sync_playwright() as p:
   browser=p.chromium.launch(headless=True);context=browser.new_context(viewport={'width':1440,'height':1100});errors=[];accept=[True]
   def new_page():
    page=context.new_page();page.on('pageerror',lambda error:errors.append(str(error)));page.on('dialog',lambda dialog:dialog.accept() if accept[0] else dialog.dismiss());page.goto('http://127.0.0.1:8889');page.wait_for_function('Object.keys(status).length>0');return page
   def load(page,did):page.evaluate('async did=>{draft=await api("/api/drafts/"+did);loadDraft();}',did)
   def edit_threads(page,text):
    page.evaluate("goWorkspace(2)")
    if page.locator('#editFields').is_hidden():page.locator('#previewToggle').click()
    fill_body(page,text)
   a=new_page();a.locator('#manualStart').click();a.locator('#title').fill('두 창 저장 테스트');fill_body(a,'네이버 본문은 보존해요.');a.locator('#threadsTab').click();fill_body(a,'처음 스레드');a.locator('#save').click();expect(a.locator('#saveState')).to_have_text('저장 완료');did=a.evaluate('draft.id')
   b=new_page();load(b,did);expect(b.locator('#threadsTab')).to_have_attribute('aria-selected','true');edit_threads(b,'B 창에서 남긴 소중한 초안')
   edit_threads(a,'A 창의 최신 저장 원고');a.locator('#save').click();expect(a.locator('#saveState')).to_have_text('저장 완료')
   b.locator('#save').click();expect(b.locator('#saveConflict')).to_be_visible();expect(b.locator('#body')).to_have_value('B 창에서 남긴 소중한 초안');assert b.evaluate('JSON.parse(localStorage.getItem("dajeong-recovery")).draft.threads')=='B 창에서 남긴 소중한 초안'
   assert b.evaluate('async did=>(await api("/api/drafts/"+did)).threads',did)=='A 창의 최신 저장 원고'
   for theme in ('light','dark'):
    b.evaluate('theme=>{document.documentElement.dataset.theme=theme;document.documentElement.style.colorScheme=theme}',theme)
    for width in (320,390,768,1440):b.set_viewport_size({'width':width,'height':1100});assert b.evaluate('document.documentElement.scrollWidth<=innerWidth'),(theme,width)
    b.locator('#saveConflict').screenshot(path=str(ROOT/('data/qa/save-conflict-'+theme+'.png')))
   b.locator('#saveConflictCopy').click();expect(b.locator('#saveState')).to_have_text('저장 완료');expect(b.locator('#saveConflict')).not_to_be_visible();assert b.evaluate('draft.id')!=did;expect(b.locator('#body')).to_have_value('B 창에서 남긴 소중한 초안')
   # A delayed library fetch locks navigation so it cannot overwrite a newly started story.
   b.locator('#showDrafts').click();pending=[];b.route('**/api/drafts/'+did,lambda route:pending.append(route));b.locator('.library-row').last.click();assert len(pending)==1
   expect(b.locator('#newDraft')).to_be_disabled();expect(b.locator('#prompt')).to_be_disabled();expect(b.locator('.library-row').first).to_be_disabled()
   delayed=pending.pop();response=delayed.fetch();delayed.fulfill(response=response);expect(b.locator('#modal')).not_to_be_visible();expect(b.locator('#newDraft')).to_be_enabled();b.unroute('**/api/drafts/'+did)
   # Old manual review results must not flag text that was edited while the request was in flight.
   edit_threads(b,'점검 요청 전 글');reviews=[];b.route('**/api/review',lambda route:reviews.append(route));b.evaluate('goWorkspace(3)');b.locator('#review').click();assert len(reviews)==1;edit_threads(b,'점검 중에 새롭게 고친 글')
   reviews.pop().fulfill(json={'checks':[{'level':'error','message':'STALE_REVIEW_MUST_NOT_APPEAR','field':'body','target':'body'}]});expect(b.locator('#review')).to_be_enabled();expect(b.locator('#qualityBox')).not_to_contain_text('STALE_REVIEW_MUST_NOT_APPEAR');b.unroute('**/api/review')
   c=new_page();load(c,did);edit_threads(c,'C 창의 아직 저장 안 된 글');edit_threads(a,'A 창에서 다시 저장한 최신 글');a.locator('#save').click();expect(a.locator('#saveState')).to_have_text('저장 완료')
   c.locator('#save').click();expect(c.locator('#saveConflict')).to_be_visible();accept[0]=False;c.locator('#saveConflictLoad').click();expect(c.locator('#body')).to_have_value('C 창의 아직 저장 안 된 글');accept[0]=True;c.locator('#saveConflictLoad').click();expect(c.locator('#saveConflict')).not_to_be_visible();expect(c.locator('#preview')).to_contain_text('A 창에서 다시 저장한 최신 글')
   c.route('**/api/status',lambda route:route.fulfill(json={'ai':False,'threads':True,'threads_details':{'ready':True,'media_ready':False},'naver_guard':{'blocked':False}}))
   publish=[]
   c.route('**/api/publish/threads',lambda route:(publish.append(route.request.post_data_json),route.fulfill(json={'job':'unicode-only-fixture'})))
   c.route('**/api/jobs/unicode-only-fixture',lambda route:route.fulfill(json={'state':'done','result':{'media_id':'fixture-no-publication'}}))
   c.evaluate("draft.platform_languages.threads='en'");edit_threads(c,'Mixed 한글');c.evaluate('goWorkspace(3)');c.locator('#publish').click();expect(c.locator('#qualityBox')).to_contain_text('한국어');expect(c.locator('#publish')).to_be_enabled();assert not publish
   c.evaluate('goWorkspace(2)');fill_body(c,'🌸'*300);expect(c.locator('#charCount')).to_have_text('300 / 500자');assert c.locator('#body').input_value()=='🌸'*300
   c.evaluate('goWorkspace(3)');c.locator('#publish').click();expect(c.locator('#workflow')).to_have_attribute('data-state','published');assert len(publish)==1 and publish[0]['with_images'] is False
   with urllib.request.urlopen('http://127.0.0.1:8889/api/drafts') as response:rows=json.load(response)
   assert len(rows)==2;assert not errors,errors;browser.close();print('Logic browser passed: actual stale saves, both-draft preservation, conflict dismissal/load, last editing platform, scoped Threads gate, 300 emoji, themes/mobile; SNS calls mocked')
 finally:process.terminate();process.wait(timeout=10)
