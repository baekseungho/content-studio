"""First-use isolation, interrupted jobs, honest recovery and offline text export; no paid calls."""
import io,json,os,subprocess,sys,tempfile,time,urllib.request
from pathlib import Path
from PIL import Image
from playwright.sync_api import sync_playwright,expect
ROOT=Path(__file__).resolve().parents[1]
with tempfile.TemporaryDirectory(prefix='mellow-recovery-') as folder:
 process=subprocess.Popen([sys.executable,str(ROOT/'app.py')],cwd=ROOT,env={**os.environ,'PORT':'8897','STUDIO_DATA_DIR':folder,'OPENAI_API_KEY':'','INSTAGRAM_ACCESS_TOKEN':'','THREADS_ACCESS_TOKEN':''},stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
 try:
  for _ in range(80):
   try:urllib.request.urlopen('http://127.0.0.1:8897/api/status',timeout=1).close();break
   except Exception:time.sleep(.2)
  with sync_playwright() as p:
   browser=p.chromium.launch(headless=True);page=browser.new_page(viewport={'width':1440,'height':1050},reduced_motion='reduce');errors=[];paid=[];jobs=[]
   page.on('pageerror',lambda e:errors.append(str(e)));page.on('dialog',lambda d:d.accept())
   for url in ('**/api/publish/**','**/api/writing/refine','**/api/channel/adapt'):
    page.route(url,lambda r:(paid.append(r.request.url),r.abort()))
   page.goto('http://127.0.0.1:8897');page.wait_for_function('()=>!!window.WorkspaceHelp&&!!window.GenerationRecovery&&Object.keys(status).length>0')
   page.locator('#prompt').fill('실제 사용자만의 소중한 메모');page.wait_for_timeout(850)
   snapshot=page.evaluate('JSON.stringify({draft,dirty,editEpoch,navigationEpoch,recovery:localStorage.getItem("dajeong-recovery"),pending:sessionStorage.getItem("mellow-pending-generation-v1")})')
   page.locator('#tryWorkspace').click();page.locator('#demoNext').click();page.locator('#demoBody').fill('체험에서만 바꾼 문장');page.locator('#demoSwapPhotos').click();page.locator('#demoTransfer').click();page.locator('#demoFinish').click()
   assert snapshot==page.evaluate('JSON.stringify({draft,dirty,editEpoch,navigationEpoch,recovery:localStorage.getItem("dajeong-recovery"),pending:sessionStorage.getItem("mellow-pending-generation-v1")})')
   assert not paid
   # Help works on narrow screens, in either theme and with keyboard navigation.
   qa=ROOT/'data/qa';qa.mkdir(parents=True,exist_ok=True)
   for theme,width in [('light',1440),('dark',390)]:
    page.set_viewport_size({'width':width,'height':1000});page.evaluate('theme=>document.documentElement.dataset.theme=theme',theme);page.locator('#workspaceHelp').click();expect(page.locator('.help-steps')).to_be_visible();assert page.evaluate('document.documentElement.scrollWidth<=innerWidth');assert page.locator('#modal').evaluate('n=>n.scrollWidth<=n.clientWidth');page.locator('#modal').screenshot(path=str(qa/('help-'+theme+'.png')));page.keyboard.press('Escape')
   page.set_viewport_size({'width':1440,'height':1050})
   image=io.BytesIO();Image.new('RGB',(300,200),'#bba6bd').save(image,'PNG');page.locator('#photos').set_input_files({'name':'sample.png','mimeType':'image/png','buffer':image.getvalue()});expect(page.locator('.photo')).to_have_count(1);mid=page.evaluate('draft.images[0]')
   original=page.evaluate("async()=>await api('/api/drafts',{title:'기존 원고',blog:'이전에 저장한 소중한 글',instagram:'다른 채널 원고는 복구본에 복사하면 안 돼요',prompt:'주말 카페 이야기',images:draft.images,selected_platforms:['naver','instagram'],selective_generation:true,workspace_step:2})")
   page.evaluate('d=>{draft=d;loadDraft();status.ai=true;draft.campaign_manual_checks=[{id:"b".repeat(20),text:"업체가 요청한 직접 확인 조건",quote:""}];}',original)
   # Clipboard denial still offers selectable text and a local file.
   page.evaluate("Object.defineProperty(navigator,'clipboard',{configurable:true,value:{writeText:async()=>{throw Error('denied')}}})")
   page.locator('#copy').click();expect(page.locator('#manualCopyText')).to_have_value('기존 원고\n\n이전에 저장한 소중한 글');page.locator('#selectManualCopy').click();assert page.locator('#manualCopyText').evaluate('n=>n.selectionEnd-n.selectionStart')>0
   with page.expect_download() as download:page.locator('#downloadCopyText').click()
   assert '이전에 저장한' in Path(download.value.path()).read_text(encoding='utf-8');page.locator('#closeModal').click()
   # A transport failure leaves a persistent action card; reconnect only reads status.
   page.route('**/api/drafts',lambda r:r.abort() if r.request.method=='POST' else r.continue_());page.locator('#save').click();expect(page.locator('#connectionRecovery')).to_be_visible();page.unroute('**/api/drafts');page.locator('#recheckConnection').click();expect(page.locator('#connectionRecoveryStatus')).to_contain_text('다시 보내지 않았어요');page.locator('#dismissConnectionRecovery').click()
   job='a'*32;result={'title':'다시 찾은 카페 이야기','blog':'창가에서 쉬어 갔어요.\n\n[[photo:1]]\n\n라떼가 고소했어요.','instagram':'원하지 않은 응답은 절대 적용하지 않기'};phase={'value':'disconnect'}
   def generation(route):jobs.append(route.request.post_data_json);route.fulfill(json={'job':job})
   def polling(route):
    if phase['value']=='disconnect':route.abort()
    elif phase['value']=='running':route.fulfill(json={'state':'running','stage':2,'message':'사진을 읽고 있어요.'})
    elif phase['value']=='missing':route.fulfill(json={'state':'failed','code':'job_missing','error':'없음'})
    else:route.fulfill(json={'state':'done','result':result})
   page.route('**/api/generate',generation);page.route('**/api/jobs/'+job,polling)
   page.evaluate("()=>{void generateForPlatforms(['naver'],false).catch(()=>{});}");page.wait_for_function('()=>!busy && !!sessionStorage.getItem("mellow-pending-generation-v1")');assert len(jobs)==1
   pending=page.evaluate('JSON.parse(sessionStorage.getItem("mellow-pending-generation-v1"))');assert 'instagram' not in pending['input'] and 'id' not in pending['input']
   page.reload();page.wait_for_function('()=>!!window.GenerationRecovery&&Object.keys(status).length>0');expect(page.locator('#generationRecovery')).to_be_visible();assert page.evaluate('draft.id')==original['id']
   page.evaluate("()=>{status.ai=true;void generateForPlatforms(['naver'],false);}");page.wait_for_timeout(100);assert len(jobs)==1
   phase['value']='running';page.locator('#checkGenerationResult').click();expect(page.locator('#recoveryResultStatus')).to_have_text('사진을 읽고 있어요.');page.locator('#closeModal').click()
   phase['value']='done';page.locator('#checkGenerationResult').click();expect(page.locator('.recovered-preview')).to_have_count(1);assert page.evaluate('draft.blog').startswith('이전에 저장한 소중한 글')
   page.locator('#importGenerationResult').click();expect(page.locator('#leaveGuard')).to_be_visible();page.locator('#keepCurrentStory').click();assert page.evaluate('draft.id')==original['id']
   page.locator('#checkGenerationResult').click();page.locator('#importGenerationResult').click();page.locator('#leaveWithoutSaving').click();expect(page.locator('#modal')).not_to_be_visible();assert page.evaluate('draft.id') is None and page.evaluate('dirty') and page.evaluate('recoveryReady');assert page.evaluate('draft.instagram')=='';assert page.evaluate('draft.blog_documents.naver.blocks.filter(b=>b.type==="photo").map(b=>b.image_id)')==[mid];assert page.evaluate('draft.campaign_manual_state')=={};assert page.evaluate('draft.campaign_manual_checks[0].text')=='업체가 요청한 직접 확인 조건';assert page.evaluate('sessionStorage.getItem("mellow-pending-generation-v1")') is None
   saved=page.evaluate('async id=>await api("/api/drafts/"+id)',original['id']);assert saved['blog']==original['blog'];assert len(jobs)==1
   # Missing jobs restore input only, never silently request replacement prose.
   page.evaluate("()=>GenerationRecovery.begin('a'.repeat(32),['threads'],{prompt:'이전 요청 메모',images:draft.images,language:'en',channel_images:{threads:[]}})")
   phase['value']='missing';page.locator('#checkGenerationResult').click();expect(page.locator('#recoveryResultStatus')).to_contain_text('다시 요청하지 않았어요');page.locator('#restoreGenerationNotes').click();page.locator('#leaveWithoutSaving').click();assert page.evaluate('draft.prompt')=='이전 요청 메모';assert not page.evaluate('anyContent()');assert page.evaluate('draft.id') is None and len(jobs)==1
   # Channel photo selections survive recovery, but old prose/verification never does.
   page.evaluate("()=>GenerationRecovery.begin('a'.repeat(32),['threads'],{prompt:'새 Threads',images:draft.images,language:'en',channel_images:{threads:[]}})");phase['value']='done';result.clear();result.update({'threads':'A little coffee break today.'});page.locator('#checkGenerationResult').click();page.locator('#importGenerationResult').click();page.locator('#leaveWithoutSaving').click();assert page.evaluate('ChannelUI.selected("threads")')==[] and page.evaluate('draft.platform_languages.threads')=='en';assert not page.evaluate('draft.blog')
   diag=json.loads(page.evaluate('WorkspaceHelp.diagnostic()'));assert set(diag)=={'version','stage','platform','busy','unsaved','temporary_copy','photo_count','text_chars','connection_error','pending_generation'};assert '이전 요청 메모' not in json.dumps(diag)
   # A closed result view cannot be resurrected by its late network response.
   page.evaluate("()=>GenerationRecovery.begin('a'.repeat(32),['threads'],{prompt:'다른 요청',images:[],language:'ko'})");page.unroute('**/api/jobs/'+job);late=[];page.route('**/api/jobs/'+job,lambda r:late.append(r));page.locator('#checkGenerationResult').click();page.locator('#closeModal').click();late.pop().fulfill(json={'state':'done','result':{'threads':'늦은 결과'}});page.wait_for_timeout(100);assert page.evaluate('draft.threads')=='A little coffee break today.';expect(page.locator('#modal')).not_to_be_visible()
   # A successful generation clears its pending reference only after a recovery copy exists.
   page.locator('#forgetGeneration').click();page.locator('#confirmForgetGeneration').click();page.unroute('**/api/jobs/'+job);page.route('**/api/jobs/'+job,polling)
   page.evaluate("async()=>{await generateForPlatforms(['threads'],false);}");expect(page.locator('#generationRecovery')).not_to_be_visible();assert page.evaluate('recoveryReady') and len(jobs)==2
   # Storage quota failure keeps a visible warning/reference until the current story is saved.
   page.evaluate("()=>{window.originalSetItem=Storage.prototype.setItem;Storage.prototype.setItem=function(key,value){if(key==='dajeong-recovery')throw new DOMException('full','QuotaExceededError');return originalSetItem.call(this,key,value);};}")
   page.evaluate("async()=>{await generateForPlatforms(['threads'],false);}");expect(page.locator('#generationRecovery')).to_contain_text('임시 보관에 실패');assert not page.evaluate('recoveryReady') and len(jobs)==3
   page.evaluate('()=>{Storage.prototype.setItem=window.originalSetItem;}');page.locator('#save').click();expect(page.locator('#saveState')).to_have_text('저장 완료');expect(page.locator('#generationRecovery')).not_to_be_visible()
   # A malformed session record must not crash load or replace the real story.
   page.evaluate("sessionStorage.setItem('mellow-pending-generation-v1',JSON.stringify({version:1,job:'a'.repeat(32),platforms:['naver'],input:{images:'broken',prompt:42,language:'ko'}}))");page.reload();page.wait_for_function('()=>!!window.GenerationRecovery');expect(page.locator('#generationRecovery')).not_to_be_visible()
   assert not errors,errors;assert not paid,paid;assert len(jobs)==3
   browser.close();print('Recovery passed: isolated demo, themes/mobile, denied clipboard fallback/download, disconnect/reconnect without retry, interrupted generation reload, no duplicate POST, running/missing/completed jobs, dirty leave guard, separate unsaved import, stable photo IDs, selected-channel isolation, input-only restore, manual mission preservation, safe diagnostics, late closed-view protection, storage quota warning/save, malformed session rejection. No paid calls or publication.')
 finally:process.terminate();process.wait(timeout=10)
