"""Exercise the focused workspace with isolated storage and mocked generation only."""
import io, json, os, subprocess, sys, tempfile, time, urllib.request
from pathlib import Path
from PIL import Image
from playwright.sync_api import sync_playwright, expect
ROOT=Path(__file__).resolve().parents[1]
def fill_body(page,text):
 if page.evaluate('tab')!='blog':page.locator('#body').fill(text);return
 page.evaluate('text=>{const prior=BlockWorkspace.ensure();const doc=StoryBlocks.create(text,StoryBlocks.photos(prior),draft[titleKey()],prior.template,prior);BlockWorkspace.commit(doc);BlockWorkspace.refresh();}',text)
with tempfile.TemporaryDirectory(prefix='mellow-workspace-') as directory:
 process=subprocess.Popen([sys.executable,str(ROOT/'app.py')],cwd=ROOT,env={**os.environ,'PORT':'8891','STUDIO_DATA_DIR':directory,'OPENAI_API_KEY':'','INSTAGRAM_ACCESS_TOKEN':'','THREADS_ACCESS_TOKEN':''},stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
 try:
  for _ in range(80):
   try:urllib.request.urlopen('http://127.0.0.1:8891/api/status',timeout=1).close();break
   except Exception:time.sleep(.2)
  with sync_playwright() as p:
   browser=p.chromium.launch(headless=True);page=browser.new_page(viewport={'width':1440,'height':1050},reduced_motion='reduce');errors=[];calls=[]
   page.on('pageerror',lambda e:errors.append(str(e)));page.on('dialog',lambda d:d.accept())
   page.goto('http://127.0.0.1:8891');page.wait_for_function('Object.keys(status).length>0')
   expect(page.locator('#composeCard')).to_be_visible();expect(page.locator('#resultCard')).not_to_be_visible();expect(page.locator('#transferCard')).not_to_be_visible()
   assert page.locator('textarea:visible').count()==1
   assert page.evaluate('(()=>{const ids=[...document.querySelectorAll("[id]")].map(x=>x.id);return ids.length===new Set(ids).size})()')
   qa=ROOT/'data/qa';qa.mkdir(parents=True,exist_ok=True)
   page.screenshot(path=str(qa/'workspace-prepare-light.png'),full_page=True)
   page.locator('#prompt').fill('성수 카페에서 보낸 오후. 창가 자리가 좋았어요.')
   page.locator('[data-example="카페"]').click();assert page.locator('#prompt').input_value().startswith('성수 카페')
   page.locator('#destinationChoices input[value=instagram]').check()
   expect(page.locator('#generationSummary')).to_contain_text('인스타그램')
   image=io.BytesIO();Image.new('RGB',(640,480),'#b6b2ca').save(image,'PNG')
   page.locator('#photos').set_input_files([{'name':'cafe.png','mimeType':'image/png','buffer':image.getvalue()}]);expect(page.locator('.photo')).to_have_count(1)
   page.locator('#writingOptions>summary').click();page.locator('#language').select_option('en');page.locator('#writingOptions>summary').click()
   page.evaluate('status.ai=true')
   def generate(route):
    calls.append(route.request.post_data_json);route.fulfill(json={'job':'workspace'})
   page.route('**/api/generate',generate)
   page.route('**/api/jobs/workspace',lambda r:r.fulfill(json={'state':'done','result':{'title':'A little coffee break','blog':'A quiet afternoon by the window.\n\n[[photo:1]]\n\nThe coffee was lovely.','instagram':'A little coffee break by the window. ☕','checks':[]}}))
   page.locator('#generate').click();expect(page.locator('#resultCard')).to_be_visible();expect(page.locator('#writingProgress')).to_have_attribute('data-state','done')
   assert len(calls)==1 and calls[0]['platforms']==['naver','instagram'] and calls[0]['language']=='en'
   expect(page.locator('#modal')).not_to_be_visible();expect(page.locator('#composeCard')).not_to_be_visible();expect(page.locator('#transferCard')).not_to_be_visible()
   page.locator('#previewToggle').click();fill_body(page,'My revised coffee story.\n\n[[photo:1]]\n\nAn afternoon to remember.')
   page.locator('#blogTab').focus();page.keyboard.press('ArrowRight');expect(page.locator('#body')).to_have_value('A little coffee break by the window. ☕')
   page.locator('#threadsTab').click();expect(page.locator('#platformEmpty')).to_be_visible();expect(page.locator('#modal')).not_to_be_visible();assert len(calls)==1
   page.locator('#blogTab').click();assert page.locator('#body').input_value().startswith('My revised coffee story.')
   page.locator('#editSettings').click();expect(page.locator('#workspaceTools')).to_be_visible();page.locator('#moreOptions>summary').click();page.locator('#facts').fill('A peaceful table by the window.');expect(page.locator('#resultCard')).to_be_visible()
   page.locator('#editSettings').click();page.locator('#backToPrepare').click();expect(page.locator('#composeCard')).to_be_visible();expect(page.locator('#facts')).to_have_value('A peaceful table by the window.')
   expect(page.locator('#destinationChoices input[value=instagram]')).to_be_checked();expect(page.locator('#language')).to_have_value('en')
   for value in ('naver','instagram'):page.locator('#destinationChoices input[value='+value+']').uncheck()
   expect(page.locator('#generate')).to_be_disabled();page.locator('#destinationChoices input[value=naver]').check();page.locator('#destinationChoices input[value=instagram]').check()
   page.locator('[data-step="2"]').click();page.locator('#continueToTransfer').click();expect(page.locator('#transferCard')).to_be_visible();expect(page.locator('#resultCard')).not_to_be_visible();expect(page.locator('#publish')).to_be_visible();expect(page.locator('#transferExpectation')).to_contain_text('마지막 발행')
   page.wait_for_function('!reviewInFlight');page.locator('#saveWorkspace').click();expect(page.locator('#saveState')).to_have_text('저장 완료');saved=page.evaluate('draft.id')
   with urllib.request.urlopen('http://127.0.0.1:8891/api/drafts/'+saved) as response:stored=json.load(response)
   assert stored['selected_platforms']==['naver','instagram'] and stored['workspace_step']==3
   assert stored['instagram']=='A little coffee break by the window. ☕'
   page.screenshot(path=str(qa/'workspace-transfer-light.png'),full_page=True)
   page.locator('#showDrafts').click();expect(page.locator('#modalTitle')).to_have_text('내 글');page.get_by_role('button',name='게시 기록',exact=True).click();expect(page.locator('#modalBody')).to_contain_text('아직 기록한 게시물이 없어요')
   page.get_by_role('button',name='보관한 글',exact=True).click();page.locator('.library-row').first.click();expect(page.locator('#transferCard')).to_be_visible()
   page.locator('#backToEdit').click();page.locator('#previewToggle').click();fill_body(page,'Recovered story from this browser.');expect(page.locator('#saveState')).to_have_text('임시 보관됨')
   page.reload();page.wait_for_function('Object.keys(status).length>0');expect(page.locator('#resultCard')).to_be_visible();expect(page.locator('#body')).to_have_value('Recovered story from this browser.');expect(page.locator('#destinationChoices input[value=instagram]')).to_be_checked()
   # A failed mission must navigate to a visible, editable field in the preparation screen.
   page.locator('#backToPrepare').click();page.locator('#campaignMode').click();page.locator('#missionDetails').evaluate('el=>el.open=true');page.locator('#campaign_min_chars').fill('2000');page.locator('#campaign_max_chars').fill('1000')
   page.evaluate('validateLength();focusIssue({field:"campaign_min_chars"})');expect(page.locator('#campaign_min_chars')).to_be_visible();expect(page.locator('#lengthError')).to_contain_text('최소 글자 수')
   page.locator('#campaign_max_chars').fill('0');page.locator('#personalMode').click()
   for theme in ('light','dark'):
    page.evaluate('theme=>{document.documentElement.dataset.theme=theme;document.documentElement.style.colorScheme=theme}',theme)
    for step in (1,2,3):
     page.evaluate('step=>setWorkflow(step)',step)
     for width in (320,390,768,1440):
      page.set_viewport_size({'width':width,'height':1050});assert page.evaluate('document.documentElement.scrollWidth<=innerWidth'),(theme,step,width)
     page.evaluate('window.scrollTo(0,0)');page.screenshot(path=str(qa/f'workspace-{step}-{theme}.png'),full_page=True)
     page.set_viewport_size({'width':390,'height':844});page.screenshot(path=str(qa/f'workspace-{step}-{theme}-mobile.png'),full_page=True)
   assert not errors,errors
   assert len(calls)==1,'Navigation or review triggered extra generation'
   # Empty channel creation and failed jobs must remain recoverable, without publishing.
   page.locator('#newDraft').click();expect(page.locator('#leaveGuard')).to_be_visible();page.locator('#leaveWithoutSaving').click();expect(page.locator('#composeCard')).to_be_visible();expect(page.locator('#language')).to_have_value('en')
   page.locator('#destinationChoices input[value=naver]').uncheck();page.locator('#destinationChoices input[value=instagram]').check()
   page.locator('#manualStart').click();expect(page.locator('#title')).not_to_be_visible();fill_body(page,'A manually written caption.');assert page.evaluate('activePlatform()')=='instagram'
   page.locator('#backToPrepare').click();page.locator('#prompt').fill('A new story.');page.evaluate('status.ai=true')
   page.route('**/api/jobs/workspace',lambda r:r.fulfill(json={'state':'failed','error':'Test: connection interrupted.'}))
   page.locator('#generate').click();expect(page.locator('#writingProgress')).to_have_attribute('data-state','running');expect(page.locator('#saveWorkspace')).to_be_disabled();expect(page.locator('[data-step="1"]')).to_be_disabled();expect(page.locator('#writingProgress')).to_have_attribute('data-state','error');expect(page.locator('#writingMessage')).to_contain_text('connection interrupted')
   expect(page.locator('#body')).to_have_value('A manually written caption.');expect(page.locator('#backToPrepare')).to_be_enabled();page.locator('#backToPrepare').click();expect(page.locator('#prompt')).to_have_value('A new story.')
   assert len(calls)==2 and calls[-1]['platforms']==['instagram']
   assert not errors,errors
   browser.close();print('Workspace passed: staged UI, early channel selection, one explicit generation, channel isolation, draft roundtrip, recovery, field navigation, library, light/dark and 320-1440px.')
 finally:process.terminate();process.wait(timeout=10)
