"""Real MV3 worker and local app; blog pages are fixtures, never public writes."""
import ast,base64,io,json,os,re,subprocess,sys,tempfile,time,urllib.error,urllib.request
from pathlib import Path
from PIL import Image
from playwright.sync_api import sync_playwright,expect
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT));sys.path.insert(0,str(ROOT/'tests'))
from test_extension import FIXTURE
from test_tistory import FIXTURE as TISTORY
parsed=ast.parse((ROOT/'tests/extension_easy_flow_check.py').read_text(encoding='utf-8'))
TOOLBAR=next(ast.literal_eval(node.value) for node in parsed.body if isinstance(node,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='FONT_TOOLBAR' for t in node.targets))
with tempfile.TemporaryDirectory(prefix='mellow-transfer-upgrade-') as folder:
 data=Path(folder)/'data';base='http://127.0.0.1:8891'
 process=subprocess.Popen([sys.executable,str(ROOT/'app.py')],cwd=ROOT,env={**os.environ,'PORT':'8891','STUDIO_DATA_DIR':str(data),'OPENAI_API_KEY':'','NAVER_BLOG_ID':'test_fixture'},stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
 try:
  for _ in range(60):
   try:
    with urllib.request.urlopen(base) as response:html=response.read().decode('utf-8')
    break
   except Exception:time.sleep(.2)
  token=re.search('name="studio-token" content="([^"]+)"',html)[1]
  def post(path,body):
   req=urllib.request.Request(base+path,data=json.dumps(body).encode(),headers={'Content-Type':'application/json','X-Studio-Token':token})
   with urllib.request.urlopen(req,timeout=10) as response:return json.load(response)
  image=io.BytesIO();Image.new('RGB',(8,8),'green').save(image,'PNG');mid=post('/api/upload',{'data':base64.b64encode(image.getvalue()).decode()})['id']
  def create(title):return post('/api/drafts',{'title':title,'blog':'고유한 첫 문단을 유지해요.\n\n[[photo:1]]\n\n'+'\n'.join('입력 단계 확인용 문장 '+str(i)+' 🌿' for i in range(30)),'images':[mid],'template':'reference'})
  first=create('결과 기록 전용 복구 테스트')
  with sync_playwright() as p:
   ext=str(ROOT/'chrome-extension');context=p.chromium.launch_persistent_context(str(Path(folder)/'browser'),channel='chromium',headless=True,args=['--disable-extensions-except='+ext,'--load-extension='+ext])
   try:
    context.route('https://blog.naver.com/**',lambda route:route.fulfill(content_type='text/html; charset=utf-8',body=TOOLBAR+FIXTURE));context.route('https://my-blog.tistory.com/**',lambda route:route.fulfill(content_type='text/html; charset=utf-8',body=TISTORY));context.route('https://media.test/**',lambda route:route.fulfill(content_type='image/png',body=image.getvalue()))
    worker=context.service_workers[0] if context.service_workers else context.wait_for_event('serviceworker');ext_id=worker.url.split('/')[2]
    worker.evaluate("""async base=>{
     await chrome.storage.local.set({pairedBase:base});self.progressMessages=[];self.injectedKeys=[];self.transfers=[];self.receivedTokens=[];self.reportMode='before';self.reportFailures=2;
     const send=request;request=async(...args)=>{if(args[1]==='/api/extension/report'&&self.reportFailures>0){self.reportFailures--;if(self.reportMode==='after')await send(...args);throw Error('fixture lost response');}const result=await send(...args);if(args[1]==='/api/extension/redeem')self.receivedTokens.push(result.report_token);return result;};
     const execute=chrome.scripting.executeScript.bind(chrome.scripting);chrome.scripting.executeScript=async options=>{if(options.args?.[0]==='fill'){self.injectedKeys.push(Object.keys(options.args[1]));self.transfers.push({id:options.args[1].transferId,tabId:options.target.tabId,frameId:options.target.frameIds[0]});}return execute(options);};
     chrome.storage.onChanged.addListener(changes=>{if(changes.lastStatus?.newValue?.message)self.progressMessages.push(changes.lastStatus.newValue.message);});
    }""",base)
    setup=context.new_page();setup.goto('chrome-extension://'+ext_id+'/popup.html')
    blog=context.new_page();blog.goto('https://blog.naver.com/test_fixture?Redirect=Write&')
    untouched=context.new_page();untouched.goto('https://blog.naver.com/other_blog?Redirect=Write&');untouched.locator('.se-section-documentTitle').evaluate("el=>el.textContent='건드리면 안 되는 다른 블로그'")
    app=context.new_page();app.goto(base+'/#extension='+ext_id);expect(app.locator('#title')).to_have_value(first['title'],timeout=15000)
    # A pasted code cannot type into a different blog, and remains unused.
    ticket=post('/api/naver/handoff',{'id':first['id']});wrong_id=worker.evaluate("async()=>(await chrome.tabs.query({url:'https://blog.naver.com/other_blog*'}))[0].id")
    wrong=worker.evaluate('message=>runFill(message)',{'tabId':wrong_id,'base':base,'channel':'naver','code':ticket['code']})
    assert not wrong['codeConsumed'] and '다른 글쓰기' in wrong['message'],wrong
    metadata=worker.evaluate("args=>request(args.base,'/api/extension/inspect',{code:args.code})",{'base':base,'code':ticket['code']});assert metadata['writer_url'].startswith('https://blog.naver.com/test_fixture')
    pages=len(context.pages);app.locator('#publish').click();expect(app.locator('#publish')).to_be_enabled(timeout=60000)
    assert len(context.pages)==pages,'A new tab was opened despite one exact blank editor';expect(blog.locator('img.se-image-resource')).to_have_count(1)
    expect(app.locator('#naverDiagnostic')).to_contain_text('기록만 다시');expect(app.get_by_role('button',name='결과 확인·기록 다시 보내기')).to_be_visible()
    state=worker.evaluate("()=>chrome.storage.session.get(['pendingReports','activeTransfer'])");assert len(state['pendingReports'])==1 and not state.get('activeTransfer')
    before=blog.locator('.se-section-text').all_inner_texts()
    try:post('/api/naver/handoff',{'id':first['id'],'repeat_confirm':True});raise AssertionError('Duplicate in-flight handoff allowed')
    except urllib.error.HTTPError as error:
     assert error.code==409;error.close()
    # Formatting has its own outcome and must not replace the pending transfer receipt.
    first_tab=worker.evaluate("async()=>{const tabs=await chrome.tabs.query({url:'https://blog.naver.com/test_fixture*'});return tabs[0].id;}")
    formatted=worker.evaluate('id=>formatOnly(id)',first_tab);assert formatted['ok'],formatted
    app.get_by_role('button',name='결과 확인·기록 다시 보내기').click();expect(app.locator('#naverDiagnostic')).not_to_contain_text('기록만 다시')
    assert worker.evaluate("async()=>(await chrome.storage.session.get('pendingReports')).pendingReports.length")==0
    assert blog.locator('.se-section-text').all_inner_texts()==before;expect(blog.locator('img.se-image-resource')).to_have_count(1)
    guard=json.loads((data/'naver-guard.json').read_text(encoding='utf-8'));assert guard['completed']==[first['id']] and len(guard['attempts'])==1
    # An acknowledged report with a lost HTTP response is retried idempotently.
    guard['attempts']=[stamp-61 for stamp in guard['attempts']];(data/'naver-guard.json').write_text(json.dumps(guard),encoding='utf-8')
    second=create('기록 응답만 유실된 경우');app.evaluate('async did=>{draft=await api("/api/drafts/"+did);loadDraft();}',second['id'])
    second_blog=context.new_page();second_blog.goto('https://blog.naver.com/test_fixture?Redirect=Write&');worker.evaluate("()=>{self.reportMode='after';self.reportFailures=1;}")
    pages=len(context.pages);app.locator('#publish').click();expect(app.locator('#publish')).to_be_enabled(timeout=60000);assert len(context.pages)==pages
    expect(second_blog.locator('img.se-image-resource')).to_have_count(1);expect(app.locator('#workflow')).to_have_attribute('data-state','ready')
    assert worker.evaluate("async()=>(await chrome.storage.session.get('pendingReports')).pendingReports.length")==0
    assert blog.locator('.se-section-text').all_inner_texts()==before;expect(untouched.locator('.se-section-documentTitle')).to_have_text('건드리면 안 되는 다른 블로그')
    old_result=worker.evaluate('message=>retryReports(message)',{'draftId':first['id'],'channel':'naver'})
    assert old_result['ok'] and old_result['result']['draftId']==first['id']
    keys=worker.evaluate('self.injectedKeys');assert len(keys)==2 and all(set(row)=={'title','body','photos','format','transferId'} for row in keys)
    messages=worker.evaluate('self.progressMessages');assert any('본문 입력' in message for message in messages),messages
    # Recover a finished page checkpoint using stored operation metadata only.
    # This is the path used when a worker response disappears; it never invokes fill again.
    second_before=second_blog.locator('.se-section-text').all_inner_texts()
    recovered=worker.evaluate("""async args=>{const base=args.base,transfer=self.transfers.at(-1);await chrome.storage.session.set({activeTransfer:{...transfer,base,draftId:args.draftId,channel:'naver',phase:'input',reportToken:self.receivedTokens.at(-1),started:Date.now(),updated:Date.now()}});return currentStatus();}""",{'base':base,'draftId':second['id']})
    assert recovered['ok'] and recovered['contentReady'];assert len(worker.evaluate('self.injectedKeys'))==2;assert second_blog.locator('.se-section-text').all_inner_texts()==second_before
    assert not worker.evaluate("async()=>(await chrome.storage.session.get('activeTransfer')).activeTransfer")
    # Tistory uses its own blank tab and can repair formatting without inserting content again.
    app.locator('#tistoryTab').click();app.locator('#tistoryUrl').evaluate("el=>{el.value='https://my-blog.tistory.com';el.dispatchEvent(new Event('input'));}")
    tistory=context.new_page();tistory.goto('https://my-blog.tistory.com/manage/newpost/');pages=len(context.pages)
    app.locator('#publish').click();expect(app.locator('#publish')).to_be_enabled(timeout=60000);assert len(context.pages)==pages;expect(tistory.locator('#content img')).to_have_count(1)
    snapshot=tistory.locator('#content').text_content();tistory.locator('#content p').first.evaluate("el=>{el.style.textAlign='left';el.style.fontFamily='Arial';el.style.fontSize='11px';}")
    tistory_id=worker.evaluate("async()=>(await chrome.tabs.query({url:'https://my-blog.tistory.com/*'}))[0].id")
    result=worker.evaluate('id=>formatOnly(id)',tistory_id);assert result['ok'],result;assert tistory.locator('#content').text_content()==snapshot;expect(tistory.locator('#content img')).to_have_count(1)
    assert tistory.locator('#content p').first.evaluate('el=>getComputedStyle(el).textAlign')=='center'
    # Two simultaneous commands claim the worker before the first asynchronous read.
    guard=json.loads((data/'naver-guard.json').read_text(encoding='utf-8'));guard['attempts']=[stamp-61 for stamp in guard['attempts']];(data/'naver-guard.json').write_text(json.dumps(guard),encoding='utf-8')
    third=create('동시 요청 첫 원고');fourth=create('동시 요청 두 번째 원고');one=post('/api/naver/handoff',{'id':third['id']});two=post('/api/naver/handoff',{'id':fourth['id']})
    concurrent_blog=context.new_page();concurrent_blog.goto('https://blog.naver.com/test_fixture?Redirect=Write&');target_id=worker.evaluate("async()=>{const tabs=await chrome.tabs.query({url:'https://blog.naver.com/*'});return tabs.at(-1).id;}")
    results=worker.evaluate("messages=>Promise.all([currentStatus(),...messages.map(message=>localMessage(message).catch(error=>({blockedByBusy:true,message:error.message})))]).then(results=>results.slice(1))",[{'type':'fill','base':base,'channel':'naver','tabId':target_id,'code':one['code']},{'type':'fill','base':base,'channel':'naver','tabId':target_id,'code':two['code']}])
    assert results[0]['ok'] and results[1]['blockedByBusy'],results;expect(concurrent_blog.locator('img.se-image-resource')).to_have_count(1)
    unused=worker.evaluate("args=>request(args.base,'/api/extension/inspect',{code:args.code})",{'base':base,'code':two['code']});assert unused['photo_count']==1
    setup.locator('#formatOnly').wait_for(state='visible');setup.screenshot(path=str(ROOT/'data/qa/extension-upgrade-popup.png'),full_page=True)
    diagnostic=worker.evaluate("async()=>(await chrome.storage.session.get('lastDiagnostic')).lastDiagnostic");assert 'report_token' not in json.dumps(diagnostic) and '고유한 첫 문단' not in json.dumps(diagnostic,ensure_ascii=False)
    print('Extension upgrade flow passed: exact blank-tab reuse, filled/wrong-blog preservation, live input progress, pre/post-ack report loss, report-only retry, credential isolation and Tistory format-only repair. No real blog navigation or publishing.')
   finally:context.close()
 finally:process.terminate();process.wait(timeout=10)
