"""Review the complete editing comforts with isolated data and mocked AI only."""
import io,json,os,subprocess,sys,tempfile,time,urllib.request
from pathlib import Path
from PIL import Image
from playwright.sync_api import sync_playwright,expect
ROOT=Path(__file__).resolve().parents[1]
with tempfile.TemporaryDirectory(prefix='mellow-experience-') as directory:
 process=subprocess.Popen([sys.executable,str(ROOT/'app.py')],cwd=ROOT,env={**os.environ,'PORT':'8886','STUDIO_DATA_DIR':directory,'OPENAI_API_KEY':''},stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
 try:
  for _ in range(60):
   try:urllib.request.urlopen('http://127.0.0.1:8886/api/status',timeout=1).close();break
   except Exception:time.sleep(.2)
  with sync_playwright() as p:
   browser=p.chromium.launch(headless=True);page=browser.new_page(viewport={'width':1440,'height':1100});errors=[];page.on('pageerror',lambda error:errors.append(str(error)));accept=[True];page.on('dialog',lambda dialog:dialog.accept() if accept[0] else dialog.dismiss())
   page.goto('http://127.0.0.1:8886');page.wait_for_function('Object.keys(status).length>0')
   files=[]
   for n,color in enumerate(('#cfb7ce','#a3b6aa')):
    buffer=io.BytesIO();Image.new('RGB',(640,480),color).save(buffer,'PNG');files.append({'name':str(n)+'.png','mimeType':'image/png','buffer':buffer.getvalue()})
   page.locator('#photos').set_input_files(files);expect(page.locator('.photo')).to_have_count(2);expect(page.locator('#photos')).to_be_enabled()
   page.get_by_role('button',name='사진 1 크게 보기',exact=True).click();expect(page.locator('#modal')).to_have_attribute('data-view','photo');expect(page.locator('#modalTitle')).to_have_text('사진 1 / 2')
   page.keyboard.press('ArrowRight');expect(page.locator('#modalTitle')).to_have_text('사진 2 / 2');page.keyboard.press('Escape');expect(page.locator('#modal')).not_to_be_visible()
   page.locator('#campaignMode').click();page.locator('#missionDetails').evaluate('el=>el.open=true');page.locator('#campaign_min_chars').fill('20');page.locator('#campaign_max_chars').fill('100')
   page.locator('#manualStart').click();page.locator('#title').fill('A coffee break');page.locator('#body').fill('## Heading\nAB CD\n[[photo:1]]\n#tag');expect(page.locator('#charCount')).to_have_text('11 / 100자');expect(page.locator('#lengthStatus')).to_contain_text('9자 더')
   page.locator('#campaign_count_spaces').check();expect(page.locator('#charCount')).to_have_text('12 / 100자')
   page.locator('#personalMode').click();expect(page.locator('#charCount')).to_have_text('12 / 5,000자');page.locator('#body').fill('Before Naver');page.locator('#prompt').fill('사실에 맞는 카페 기록')
   page.locator('#instaTab').click();page.locator('#body').fill('Instagram stays the same.');page.locator('#blogTab').click()
   page.evaluate("()=>{status.ai=true;draft.layout_bases.naver='original layout';draft.layout_last.naver='Before Naver';}")
   calls=[]
   def generate(route):
    calls.append(route.request.post_data_json);route.fulfill(json={'job':'experience-'+str(len(calls))})
   page.route('**/api/generate',generate)
   page.route('**/api/jobs/experience-*',lambda route:route.fulfill(json={'state':'done','result':{'title':'Generated title','blog':'Generated Naver body.','layout_bases':{'naver':'generated layout'},'layout_last':{'naver':'Generated Naver body.'}}}))
   def regenerate():
    page.locator('#generate').click();page.locator('#startSelectedGeneration').click();expect(page.locator('#generate')).to_be_enabled();expect(page.locator('#preview')).to_contain_text('Generated Naver body.')
   regenerate();expect(page.locator('#undoGeneration')).to_be_visible();page.locator('#undoGeneration').click();expect(page.locator('#preview')).to_contain_text('Before Naver');assert page.evaluate('draft.instagram')=='Instagram stays the same.';assert page.evaluate('draft.layout_bases.naver')=='original layout';expect(page.locator('#undoGeneration')).not_to_be_visible()
   regenerate();page.locator('#previewToggle').click();page.locator('#body').fill('My manual edits after generation');accept[0]=False;page.locator('#undoGeneration').click();expect(page.locator('#body')).to_have_value('My manual edits after generation');accept[0]=True;page.locator('#undoGeneration').click();expect(page.locator('#body')).to_have_value('Before Naver');assert len(calls)==2
   page.locator('#moreOptions').evaluate('el=>el.open=true');page.locator('#placePanel').evaluate('el=>el.open=true');page.locator('#placeManual').evaluate('el=>el.open=true');page.locator('#placeName').fill('성수 작은 카페');page.locator('#placeAddress').fill('서울 성동구 테스트로 1');page.locator('#placeUseManual').click();page.locator('#title').fill('다시 찾을 카페 이야기');page.locator('#save').click();expect(page.locator('#saveState')).to_have_text('저장 완료')
   first_id=page.evaluate('draft.id');page.locator('#newDraft').click();page.locator('#threadsTab').click();page.locator('#manualStart').click();page.locator('#body').fill('🌸');expect(page.locator('#charCount')).to_have_text('1 / 500자');expect(page.locator('#editorLabel')).to_have_text('Threads 초안');page.locator('#save').click();expect(page.locator('#saveState')).to_have_text('저장 완료')
   page.locator('#showDrafts').click();expect(page.locator('.library-row')).to_have_count(2);page.locator('#librarySearch').fill('성수');expect(page.locator('.library-row')).to_have_count(1);expect(page.locator('.library-row')).to_contain_text('다시 찾을 카페');page.locator('#libraryPlatform').select_option('threads');expect(page.locator('.library-empty')).to_be_visible();page.locator('#librarySearch').fill('');expect(page.locator('.library-row')).to_have_count(1);page.locator('.library-row').click();expect(page.locator('#threadsTab')).to_have_attribute('aria-selected','true')
   page.locator('#previewToggle').click();page.locator('#body').fill('Saved in this browser');expect(page.locator('#saveState')).to_have_text('임시 보관됨');assert page.evaluate('JSON.parse(localStorage.getItem("dajeong-recovery")).draft.threads')=='Saved in this browser'
   page.evaluate("()=>{window.realStorageSet=Storage.prototype.setItem;Storage.prototype.setItem=function(k,v){if(k==='dajeong-recovery')throw Error('quota');return realStorageSet.call(this,k,v)};}");page.locator('#body').fill('Do not lose these edits');expect(page.locator('#saveState')).to_have_text('임시 보관 불가');expect(page.locator('#body')).to_have_value('Do not lose these edits');page.evaluate('()=>{Storage.prototype.setItem=realStorageSet;persistRecovery();}');expect(page.locator('#saveState')).to_have_text('임시 보관됨')
   for theme in ('light','dark'):
    page.evaluate('theme=>{document.documentElement.dataset.theme=theme;document.documentElement.style.colorScheme=theme}',theme)
    for width in (320,390,768,1440):
     page.set_viewport_size({'width':width,'height':1100});assert page.evaluate('document.documentElement.scrollWidth<=innerWidth'),(theme,width)
    page.locator('#showDrafts').click();page.locator('#libraryPlatform').select_option('');page.locator('#librarySearch').fill('')
    for width in (320,390,768,1440):
     page.set_viewport_size({'width':width,'height':1100});assert page.evaluate('document.documentElement.scrollWidth<=innerWidth'),('library',theme,width)
    page.screenshot(path=str(ROOT/('data/qa/experience-library-'+theme+'.png')));page.locator('#closeModal').click();page.evaluate('window.scrollTo(0,0)');page.screenshot(path=str(ROOT/('data/qa/experience-editor-'+theme+'.png')),full_page=True)
   # Exactly two explicit generations. Viewer/library/undo/counts/recovery use no AI calls.
   assert len(calls)==2 and all(row['platforms']==['naver'] for row in calls)
   with urllib.request.urlopen('http://127.0.0.1:8886/api/drafts') as response:rows=json.load(response)
   assert len(rows)==2 and any(row['id']==first_id and row['place']=='성수 작은 카페' for row in rows)
   assert not errors,errors;browser.close();print('Experience checks passed: photo viewer, exact counts, isolated undo and edit confirmation, searchable visual library, last platform, honest recovery states, themes/mobile and no incidental AI calls')
 finally:process.terminate();process.wait(timeout=10)
