"""Review merchant requirements end to end, with isolated storage and mocked writing."""
import json,os,subprocess,sys,tempfile,time,urllib.request
from pathlib import Path
from playwright.sync_api import sync_playwright,expect
ROOT=Path(__file__).resolve().parents[1]
GUIDE='업체명: 메모카페\n제공 내역: 2인 식사권\n제목 키워드: 성수카페, 메모카페\n본문 키워드: 크림라떼 (각 3회 이상)\n본문: 공백 제외 2,000~3,000자\n사진 5장 이상\n해시태그: #성수 #메모카페\n필수 문구: 예약 후 방문해 주세요.\n금지 표현: 최고, 무조건 추천\n지도와 배너를 넣어 주세요.\n마감일: 11/30까지 게시'
with tempfile.TemporaryDirectory(prefix='mellow-missions-') as folder:
 process=subprocess.Popen([sys.executable,str(ROOT/'app.py')],cwd=ROOT,env={**os.environ,'PORT':'8893','STUDIO_DATA_DIR':folder,'OPENAI_API_KEY':'','NAVER_BLOG_ID':'fixture','THREADS_ACCESS_TOKEN':'','INSTAGRAM_ACCESS_TOKEN':''},stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
 try:
  for _ in range(70):
   try:urllib.request.urlopen('http://127.0.0.1:8893/api/status',timeout=1).close();break
   except Exception:time.sleep(.2)
  with sync_playwright() as p:
   browser=p.chromium.launch(headless=True);page=browser.new_page(viewport={'width':1440,'height':1050},reduced_motion='reduce');errors=[];calls=[]
   page.on('pageerror',lambda e:errors.append(str(e)));page.on('dialog',lambda d:d.accept())
   page.goto('http://127.0.0.1:8893');page.wait_for_function('!!window.CampaignUI && Object.keys(status).length>0')
   page.locator('#prompt').fill('창가에서 직접 마신 크림라떼가 고소했어요.');page.locator('#campaignMode').click();page.locator('#campaign_brief').fill(GUIDE);page.locator('#parseCampaign').click();expect(page.locator('#campaignSuggestions')).to_be_visible();page.screenshot(path=str(ROOT/'data/qa/missions-suggestions.png'),full_page=True)
   expect(page.locator('#campaignSuggestions input[type=checkbox]:checked')).to_have_count(0);expect(page.locator('#applyCampaignSuggestions')).to_be_disabled();assert not calls
   page.locator('#campaignSuggestions').get_by_role('button',name='모두 선택',exact=True).click();page.locator('#applyCampaignSuggestions').click();expect(page.locator('#campaign_min_chars')).to_have_value('2000');expect(page.locator('#campaign_max_chars')).to_have_value('3000');expect(page.locator('#campaign_count_spaces')).not_to_be_checked();expect(page.locator('#body_keywords')).to_have_value('크림라떼');expect(page.locator('#keyword_min_count')).to_have_value('3')
   expect(page.locator('#confirmedConditions')).to_contain_text('공백 제외');assert len(page.evaluate('draft.campaign_manual_checks'))==2
   page.locator('#disclosure').select_option('experience');page.locator('#missionDetails').evaluate('e=>e.open=true');page.locator('#campaign_max_chars').fill('1000');expect(page.locator('#campaignPreflight')).to_contain_text('최소 2,000자가 최대 1,000자보다 커요');expect(page.locator('#campaign_min_chars')).to_have_attribute('aria-invalid','true');expect(page.locator('#campaign_max_chars')).to_have_attribute('aria-invalid','true')
   page.evaluate('status.ai=true');page.route('**/api/generate',lambda route:(calls.append(route.request.post_data_json),route.fulfill(json={'job':'mission'})))
   page.route('**/api/jobs/mission',lambda route:route.fulfill(json={'state':'done','result':{'title':'성수카페 메모카페 후기','blog':'크림라떼를 마셨어요. 여기는 최 고라고 쓰면 안 되죠.','checks':[],'needs_more_notes':True}}))
   page.locator('#generate').click();assert not calls
   page.locator('#campaign_max_chars').fill('3000');page.locator('#title_keywords').fill('성수카페, 최고');expect(page.locator('#campaignPreflight')).to_contain_text('꼭 넣는 조건과 쓰지 않는 조건')
   page.locator('#generate').click();assert not calls
   page.locator('#title_keywords').fill('성수카페, 메모카페');page.locator('#generate').click();expect(page.locator('#writingProgress')).to_have_attribute('data-state','done');assert len(calls)==1;assert calls[0]['campaign_brief_review']['hash']
   expect(page.locator('#campaignChecklist')).to_contain_text('자동 확인');expect(page.locator('#campaignChecklist')).to_contain_text('2개 남음');page.locator('#campaignChecklist').evaluate('e=>e.open=true')
   forbidden=page.locator('.mission-check-row').filter(has_text='사용하지 않을 표현 · 최고');forbidden.get_by_role('button',name='원고 고치기',exact=True).click();field=page.locator('#blockEditor textarea').first;expect(field).to_be_focused();selected=field.evaluate('e=>e.value.slice(e.selectionStart,e.selectionEnd)');assert selected.replace(' ','')=='최고',selected
   page.locator('#campaignChecklist').evaluate('e=>e.open=true');page.locator('.mission-check-row').filter(has_text='제목 · 성수카페').get_by_role('button',name='원문 보기',exact=True).click();expect(page.locator('#campaign_brief')).to_be_focused();assert '제목 키워드' in page.locator('#campaign_brief').evaluate('e=>e.value.slice(e.selectionStart,e.selectionEnd)')
   page.evaluate('goWorkspace(2)');page.locator('#campaignChecklist').evaluate('e=>e.open=true');page.locator('.manual-check-row input').first.check();expect(page.locator('.manual-check-row input').first).to_be_checked();page.wait_for_timeout(350)
   page.locator('#tistoryTab').click();page.locator('#campaignChecklist').evaluate('e=>e.open=true');expect(page.locator('.manual-check-row input').first).not_to_be_checked();page.locator('#blogTab').click();page.locator('#campaignChecklist').evaluate('e=>e.open=true');expect(page.locator('.manual-check-row input').first).to_be_checked()
   page.evaluate('BlockWorkspace.focus({})');page.locator('#blockEditor textarea').first.fill('크림라떼가 고소했어요. 직접 경험한 이야기만 적어요.');expect(page.locator('.manual-check-row input').first).not_to_be_checked()
   page.locator('#campaignChecklist').get_by_role('button',name='경험 더 적기',exact=True).click();page.locator('#experience-good').fill('한 모금 마셨을 때 고소한 향이 남았고 창가 자리가 편했어요.');page.get_by_role('button',name='경험 메모에 담기',exact=True).click();assert '고소한 향' in page.locator('#facts').input_value();assert len(calls)==1
   page.locator('#saveWorkspace').click();expect(page.locator('#saveState')).to_have_text('저장 완료');did=page.evaluate('draft.id');page.locator('#showDrafts').click();page.locator('.library-row').first.click();assert page.evaluate('draft.campaign_brief_review.hash') and len(page.evaluate('draft.campaign_manual_checks'))==2;assert page.evaluate('draft.campaign_experience.good').startswith('한 모금')
   page.locator('#campaignPanel').evaluate('e=>e.open=true');page.locator('#campaign_brief').fill(GUIDE+'\n수정한 안내');expect(page.locator('#campaignPreflight')).to_contain_text('안내문이 바뀌었어요');page.locator('#confirmCampaignManual').click();expect(page.locator('#campaignParseStatus')).to_contain_text('직접 입력한 조건')
   # A delayed old analysis must not replace a newly edited guide or its conditions.
   pending=[];page.route('**/api/campaign/parse',lambda route:pending.append(route));page.locator('#parseCampaign').click();assert len(pending)==1
   page.locator('#campaign_brief').fill(GUIDE+'\n새롭게 바뀐 안내');held=pending.pop();response=held.fetch();held.fulfill(response=response)
   expect(page.locator('#campaignParseStatus')).to_contain_text('바뀌었어요');expect(page.locator('#campaignSuggestions')).not_to_be_visible();expect(page.locator('#campaign_min_chars')).to_have_value('2000');page.unroute('**/api/campaign/parse')
   page.locator('#confirmCampaignManual').click();expect(page.locator('#campaignParseStatus')).to_contain_text('직접 입력한 조건')
   for theme in ('light','dark'):
    page.evaluate('t=>document.documentElement.dataset.theme=t',theme)
    for stage in (1,2,3):
     page.evaluate('s=>setWorkflow(s)',stage)
     for width in (320,390,768,1440):
      page.set_viewport_size({'width':width,'height':1050});assert page.evaluate('document.documentElement.scrollWidth<=innerWidth'),(theme,stage,width)
    page.evaluate('setWorkflow(1)');page.screenshot(path=str(ROOT/('data/qa/missions-'+theme+'.png')),full_page=True)
   assert not errors,errors;assert len(calls)==1
   browser.close();print('Campaign missions passed: explicit sourced selection, conflict/no-generation gates, block fix location, manual-check scoping/invalidation, experience notes, roundtrip, themes/mobile; writing mocked, no SNS publication.')
 finally:process.terminate();process.wait(timeout=10)
