"""Explicit partial edits, style preferences, cancellation, stale guard and scoped undo."""
import io,json,os,subprocess,sys,tempfile,time,urllib.request
from pathlib import Path
from PIL import Image
from playwright.sync_api import sync_playwright,expect
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from writing_edits import prepare

with tempfile.TemporaryDirectory(prefix="mellow-writing-") as folder:
 process=subprocess.Popen([sys.executable,str(ROOT/"app.py")],cwd=ROOT,env={**os.environ,"PORT":"8894","STUDIO_DATA_DIR":folder,"OPENAI_API_KEY":"","INSTAGRAM_ACCESS_TOKEN":"","THREADS_ACCESS_TOKEN":""},stdout=subprocess.DEVNULL,stderr=subprocess.PIPE)
 try:
  for _ in range(70):
   try:urllib.request.urlopen("http://127.0.0.1:8894/api/status",timeout=1).close();break
   except Exception:time.sleep(.2)
  with sync_playwright() as p:
   browser=p.chromium.launch(headless=True);page=browser.new_page(viewport={"width":1440,"height":1050},reduced_motion="reduce");errors=[];calls=[];mode={"value":"good"};results={};generation=[]
   page.on("pageerror",lambda e:errors.append(str(e)));page.on("dialog",lambda d:d.accept())
   def mock_edit(route):
    body=route.request.post_data_json;calls.append(body);req=prepare(body);jid="writing-"+str(len(calls));original=req["selected"]
    choices=["카페에서 남긴 오후 기록","크림라떼와 함께한 카페 이야기","오후의 카페, 한 잔의 기록"] if req["action"]=="titles" else ["라떼 3잔을 마셨어요." if mode["value"]=="bad" else original.replace("고소했어요","고소하더라고요").replace("좋았어요","좋더라고요").replace("I liked the cream.","I really liked that cream.")]
    results[jid]={"choices":[{"text":value} for value in choices]};route.fulfill(json={"job":jid})
   page.route("**/api/writing/refine",mock_edit)
   def mock_job(route):
    jid=route.request.url.rsplit("/",1)[-1]
    route.fulfill(json={"state":"running","message":"선택한 부분만 다듬는 중이에요.","stage":2} if mode["value"]=="waiting" else {"state":"done","result":results[jid]})
   page.route("**/api/jobs/writing-*",mock_job)
   page.route("**/api/generate",lambda route:(generation.append(route.request.post_data_json),route.fulfill(json={"job":"generation-test"})))
   page.route("**/api/jobs/generation-test",lambda route:route.fulfill(json={"state":"done","result":{"threads":"오늘의 카페 이야기","checks":[]}}))
   page.goto("http://127.0.0.1:8894");page.wait_for_function("()=>!!window.WritingUI && Object.keys(status).length>0")
   page.locator("#writingOptions").evaluate("el=>el.open=true");expect(page.locator(".voice-card")).to_have_count(5)
   page.locator("#voiceChannel").select_option("threads");page.locator('[data-voice-preset=witty]').click();assert page.evaluate("draft.voice_styles.threads.preset")=="witty" and page.evaluate("!draft.voice_styles.naver")
   page.locator("#voiceChannel").select_option("naver");page.locator("#manageVoice").click();page.locator("#voice-name").fill("나의 카페 말투");page.locator("#voice-sample").fill("라떼가 고소하더라고요. 창가 자리도 정말 좋았어요. 짧게 남기고 싶어요. ☕");page.locator("#analyzeVoice").click();expect(page.locator("#voice-formality")).to_have_value("polite");page.locator("#voice-avoid").fill("최고, 인생라떼");page.locator("#useVoice").click();expect(page.locator("#modal")).not_to_be_visible();assert page.evaluate("draft.voice_styles.naver.name")=="나의 카페 말투"
   stored=page.evaluate("async()=>await api('/api/voice-profiles')");assert stored["profiles"]["naver"]["avoid"]=="최고, 인생라떼";assert not calls
   b=io.BytesIO();Image.new("RGB",(600,400),"#b9aabf").save(b,"PNG");page.locator("#photos").set_input_files({"name":"cafe.png","mimeType":"image/png","buffer":b.getvalue()});expect(page.locator(".photo")).to_have_count(1);ids=page.evaluate("draft.images.slice()")
   source="☕ 라떼 2잔을 마셨어요. 크림이 고소했어요.\n남길 문장이에요.\n\n[[photo:1]]\n\n끝 문단도 그대로 남아요."
   page.evaluate("arg=>{draft={...fresh(),images:arg.ids,blog:arg.body,title:'카페 기록',tistory:'티스토리는 그대로',tistory_title:'다른 제목',instagram:'I liked the cream.',threads:'Threads도 그대로',selective_generation:true,workspace_step:2,voice_styles:arg.voices,platform_languages:{instagram:'en'}};loadDraft();}",{"body":source,"ids":ids,"voices":stored["profiles"]})
   page.locator("#previewToggle").click();first=page.locator(".paragraph-block textarea").first;block=page.locator(".paragraph-block").first;original=first.input_value();start=original.index("크림");end=start+len("크림이 고소했어요.")
   first.evaluate("(el,r)=>{el.focus();el.setSelectionRange(r[0],r[1]);el.dispatchEvent(new Event('select'));}",[start,end]);block.get_by_role("button",name="이 부분만 AI로 다듬기",exact=True).click();assert not calls
   page.locator("#requestRefine").click();expect(page.locator("#applyRefine")).to_be_enabled();assert calls[-1]["target"]["start"]==start;assert "티스토리는 그대로" not in json.dumps(calls[-1],ensure_ascii=False)
   expect(page.locator("#refineCandidate")).to_have_value("크림이 고소하더라고요.");page.get_by_role("button",name="원문 유지 · 닫기",exact=True).click();assert page.evaluate("draft.blog")==source
   # Explicit apply, then the persistent block undo; no other channel or photo changes.
   first=page.locator(".paragraph-block textarea").first;first.evaluate("(el,r)=>{el.focus();el.setSelectionRange(r[0],r[1]);}",[start,end]);page.locator(".paragraph-block").first.get_by_role("button",name="이 부분만 AI로 다듬기",exact=True).click();page.locator("#requestRefine").click();expect(page.locator("#applyRefine")).to_be_enabled();page.locator("#applyRefine").click()
   changed=page.evaluate("draft.blog");assert changed==source.replace("크림이 고소했어요.","크림이 고소하더라고요.");assert page.evaluate("draft.tistory")=="티스토리는 그대로";assert page.evaluate("StoryBlocks.photos(BlockWorkspace.ensure())")==ids
   page.locator("#blockUndo").click();assert page.evaluate("draft.blog")==source;page.locator("#blockRedo").click();assert page.evaluate("draft.blog")==changed
   # A numeric regression blocks applying; manual repair is free and unlocks it.
   mode["value"]="bad";page.locator(".paragraph-block").first.get_by_role("button",name="이 부분만 AI로 다듬기",exact=True).click();page.locator("#requestRefine").click();expect(page.locator("#refineFeedback")).to_contain_text("숫자");expect(page.locator("#applyRefine")).to_be_disabled();n=len(calls);page.locator("#refineCandidate").fill("☕ 라떼 2잔을 마셨어요. 크림이 참 고소하더라고요.\n남길 문장이에요.");expect(page.locator("#applyRefine")).to_be_enabled();assert len(calls)==n
   # Source changes after the proposal must prevent an overwrite.
   page.evaluate("()=>{const doc=BlockWorkspace.ensure();doc.blocks[0].text+=' 직접 고친 문장.';BlockWorkspace.commit(doc);}");page.locator("#applyRefine").click();expect(page.locator("#refineFeedback")).to_contain_text("달라졌어요");expect(page.locator("#applyRefine")).to_be_disabled();page.locator("#closeModal").click()
   # A pending request can be closed; late results never mutate the source.
   mode["value"]="waiting";saved=page.evaluate("draft.blog");page.locator(".paragraph-block").first.get_by_role("button",name="이 부분만 AI로 다듬기",exact=True).click();page.locator("#requestRefine").click();expect(page.locator(".refine-progress")).to_be_visible();page.locator("#closeModal").click();page.wait_for_function("()=>busy===false");mode["value"]="good";assert page.evaluate("draft.blog")==saved
   # Optional three titles, preview updates immediately, undo restores the title.
   page.locator("#previewToggle").click();page.locator("#suggestTitles").click();page.locator("#requestRefine").click();expect(page.locator(".title-choice")).to_have_count(3);page.locator(".title-choice").nth(1).click();expect(page.locator("#applyRefine")).to_be_enabled();page.locator("#applyRefine").click();expect(page.locator("#preview h3")).to_have_text("크림라떼와 함께한 카페 이야기");page.locator("#previewToggle").click();page.locator("#blockUndo").click();expect(page.locator("#title")).to_have_value("카페 기록")
   # Empty titles and photo captions use the same scoped compare/apply boundary.
   page.evaluate("()=>{const editor=BlockWorkspace.editor;$('blockUndo').focus();editor.render();$('title').focus();}");assert page.evaluate("async()=>{await new Promise(r=>requestAnimationFrame(()=>requestAnimationFrame(r)));return document.activeElement.id;}")=="title"
   page.locator("#title").fill("");expect(page.locator("#title")).to_have_value("");page.locator("#suggestTitles").click();page.locator("#requestRefine").click();expect(page.locator("#applyRefine")).to_be_enabled();page.locator("#applyRefine").click();page.locator("#blockUndo").click();expect(page.locator("#title")).to_have_value("");page.locator("#title").fill("카페 기록")
   photo=page.locator(".photo-block").first;photo.locator(".block-caption").fill("창가 풍경이 좋았어요.");photo.get_by_role("button",name="이 부분만 AI로 다듬기",exact=True).click();page.locator("#requestRefine").click();expect(page.locator("#applyRefine")).to_be_enabled();page.locator("#applyRefine").click();expect(page.locator(".block-caption").first).to_have_value("창가 풍경이 좋더라고요.");assert page.evaluate("StoryBlocks.photos(BlockWorkspace.ensure())")==ids;page.locator("#blockUndo").click();expect(page.locator(".block-caption").first).to_have_value("창가 풍경이 좋았어요.")
   # English SNS edit, scoped undo, no mixed language, draft save/reopen preferences.
   page.locator("#instaTab").click();page.locator("#refineCaption").click();page.locator("#requestRefine").click();expect(page.locator("#applyRefine")).to_be_enabled();assert calls[-1]["language"]=="en";page.locator("#applyRefine").click();assert page.evaluate("draft.instagram")=="I really liked that cream.";page.locator("#undoTextEdit").click();assert page.evaluate("draft.instagram")=="I liked the cream."
   page.locator("#saveWorkspace").click();expect(page.locator("#saveState")).to_have_text("저장 완료");did=page.evaluate("draft.id");saved=page.evaluate("async id=>await api('/api/drafts/'+id)",did);assert saved["voice_styles"]["naver"]["name"]=="나의 카페 말투"
   # Only explicitly selected voices accompany selected generation.
   page.evaluate("async()=>{$('prompt').value='확인한 카페 경험만 남겨 주세요.';await generateForPlatforms(['threads'],true);}")
   assert len(generation)==1 and generation[0]["platforms"]==["threads"] and "naver" not in generation[0]["voice_styles"]
   page.locator("#blogTab").click();page.locator("#suggestTitles").click();page.locator("#requestRefine").click();expect(page.locator("#applyRefine")).to_be_enabled()
   for theme in ("light","dark"):
    page.evaluate("t=>document.documentElement.dataset.theme=t",theme)
    for width in (320,390,768,1440):
     page.set_viewport_size({"width":width,"height":1050});assert page.evaluate("document.documentElement.scrollWidth<=innerWidth"),(theme,width)
    page.screenshot(path=str(ROOT/("data/qa/writing-"+theme+".png")),full_page=True)
   page.locator("#closeModal").click();page.evaluate("goWorkspace(1)");page.locator("#writingOptions").evaluate("el=>el.open=true");page.locator("#manageVoice").click()
   page.screenshot(path=str(ROOT/"data/qa/voice-profile-dark.png"),full_page=True)
   assert not errors,errors;browser.close();print("Writing passed: scoped selection, explicit request/apply, cancel and late results, numeric/mission validation, manual repair without AI, stale guard, block/SNS undo, title preview, saved per-channel voice, local sample analysis, selected-channel payload, light/dark/mobile. No real AI or SNS calls.")
 finally:
  process.terminate();process.wait(timeout=10)
