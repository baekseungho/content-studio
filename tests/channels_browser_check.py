"""Per-channel media, no-cost crops, source-to-SNS proposal boundaries and posting payloads."""
import io,json,os,subprocess,sys,tempfile,time,urllib.request
from pathlib import Path
from PIL import Image
from playwright.sync_api import sync_playwright,expect
ROOT=Path(__file__).resolve().parents[1]

def photo(name,color,size):
 buffer=io.BytesIO();image=Image.new("RGB",size,color);image.paste("#d7e2cc",(0,0,size[0]//2,size[1]));image.save(buffer,"PNG");return {"name":name,"mimeType":"image/png","buffer":buffer.getvalue()}

with tempfile.TemporaryDirectory(prefix="mellow-channels-") as folder:
 process=subprocess.Popen([sys.executable,str(ROOT/"app.py")],cwd=ROOT,env={**os.environ,"PORT":"8895","STUDIO_DATA_DIR":folder,"OPENAI_API_KEY":"","INSTAGRAM_ACCESS_TOKEN":"","THREADS_ACCESS_TOKEN":""},stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
 try:
  for _ in range(80):
   try:urllib.request.urlopen("http://127.0.0.1:8895/api/status",timeout=1).close();break
   except Exception:time.sleep(.2)
  with sync_playwright() as p:
   browser=p.chromium.launch(headless=True);page=browser.new_page(viewport={"width":1440,"height":1050},reduced_motion="reduce");errors=[];ai=[];jobs={};mode={"value":"good"};publishes=[]
   page.on("pageerror",lambda e:errors.append(str(e)));page.on("dialog",lambda d:d.accept())
   page.route("**/api/generate",lambda route:route.abort())
   def adapt(route):
    request=route.request.post_data_json;ai.append(request);jid="adapt-"+str(len(ai));value="x"*510 if mode["value"]=="long" else "라떼 3잔을 마셨어요." if mode["value"]=="bad" else "The cream on this latte had a lovely nutty taste." if request["language"]=="en" else "크림이 고소하더라고요."
    jobs[jid]={"text":value,"facts_translation":""};route.fulfill(json={"job":jid})
   page.route("**/api/channel/adapt",adapt);page.route("**/api/jobs/adapt-*",lambda route:route.fulfill(json={"state":"running","message":"확인한 블로그를 새 채널에 맞추고 있어요."} if mode["value"]=="waiting" else {"state":"done","result":jobs[route.request.url.rsplit("/",1)[-1]]}))
   page.goto("http://127.0.0.1:8895");page.wait_for_function("()=>!!window.ChannelUI && Object.keys(status).length>0")
   page.locator("#photos").set_input_files([photo("wide.png","#a895ac",(800,400)),photo("tall.png","#bd9f95",(400,800)),photo("square.png","#879bac",(500,500))]);expect(page.locator(".photo")).to_have_count(3);ids=page.evaluate("draft.images.slice()")
   body="라떼 2잔을 마셨어요. 크림이 고소했어요.\n\n[[photo:1]]\n\n창가에 앉았어요.\n\n[[photo:2]]\n\n[[photo:3]]"
   page.evaluate("arg=>{draft={...fresh(),images:arg.ids,title:'카페 기록',blog:arg.body,tistory_title:'별도 제목',tistory:'다른 블로그 글',instagram:'기존 인스타그램 원고',threads:'기존 Threads 원고',selective_generation:true,workspace_step:2};loadDraft();}",{"ids":ids,"body":body})
   original=page.evaluate("JSON.stringify(draft.blog_documents.naver)");page.locator("#instaTab").click();expect(page.locator("#channelMediaPanel")).to_be_visible();expect(page.locator(".social-slide-strip button")).to_have_count(3)
   page.locator("#channelPhotoDetails").evaluate("el=>el.open=true");page.locator(".channel-photo-row").nth(2).get_by_role("button",name="첫 장으로",exact=True).click();assert page.evaluate("ChannelUI.selected('instagram')")==[ids[2],ids[0],ids[1]];assert page.evaluate("ChannelUI.selected('threads')")==ids
   page.get_by_role("button",name="이 채널에서 사진 2 빼기",exact=True).click();assert page.evaluate("ChannelUI.selected('instagram')")==[ids[2],ids[1]];assert page.evaluate("draft.images")==ids;assert page.evaluate("JSON.stringify(draft.blog_documents.naver)")==original
   page.locator("#undoChannelMedia").click();assert page.evaluate("ChannelUI.selected('instagram')")==[ids[2],ids[0],ids[1]];page.locator("#redoChannelMedia").click();assert page.evaluate("ChannelUI.selected('instagram')")==[ids[2],ids[1]]
   page.locator("#chooseChannelPhotos").click();expect(page.locator("#channelPhotoPicker input")).to_have_count(3);page.locator('#channelPhotoPicker input[value="'+ids[0]+'"]').check();page.locator("#applyChannelPhotos").click();assert page.evaluate("ChannelUI.selected('instagram')")==[ids[2],ids[1],ids[0]]
   page.locator("#channelFrame").select_option("square");page.locator(".channel-photo-row").nth(2).get_by_role("button",name="화면 맞춤",exact=True).click();page.locator("#photoFitMode").select_option("cover");page.locator("#photoPosition-x").fill("0");expect(page.locator("#applyPhotoFit")).to_be_enabled();page.locator("#applyPhotoFit").click();assert page.evaluate("draft.channel_media.instagram.adjustments[draft.images[0]].x")==0
   page.get_by_role("button",name="슬라이드 3",exact=True).click();expect(page.locator(".social-slide img")).to_be_visible();assert page.locator(".social-slide img").get_attribute("src").startswith("data:image/jpeg;base64,")
   assert len(list((Path(folder)/"media").glob("*.jpg")))==3 # previews create no derivative files
   assert not ai;page.locator("#saveWorkspace").click();expect(page.locator("#saveState")).to_have_text("저장 완료");did=page.evaluate("draft.id");saved=page.evaluate("async id=>await api('/api/drafts/'+id)",did);assert saved["channel_media"]["instagram"]["images"]==[ids[2],ids[1],ids[0]]
   page.evaluate("async id=>{draft=await api('/api/drafts/'+id);loadDraft();}",did);assert page.evaluate("draft.channel_media.instagram.frame")=="square"
   page.locator("#threadsTab").click();page.locator("#threadsPhotos").uncheck();expect(page.locator("#preview")).to_contain_text("사진 없이 글만");assert page.evaluate("ChannelUI.selected('threads')")==ids;assert page.evaluate("ChannelUI.photos('threads')")==[];page.locator("#threadsPhotos").check()
   page.locator("#chooseChannelPhotos").click();page.locator('#channelPhotoPicker input[value="'+ids[1]+'"]').uncheck();page.locator("#applyChannelPhotos").click();assert page.evaluate("ChannelUI.selected('threads')")==[ids[0],ids[2]];assert page.evaluate("ChannelUI.selected('instagram')")==[ids[2],ids[1],ids[0]]
   # Original pool edits never change already chosen SNS photographs.
   page.evaluate("()=>{goWorkspace(1);removePhoto(0);renderPhotos();markDirty();}");assert page.evaluate("draft.images")==ids[1:];assert page.evaluate("ChannelUI.selected('threads')")==[ids[0],ids[2]];page.evaluate("goWorkspace(2)")
   # Open, read and close does not call AI; applying a proposal is explicit.
   page.locator("#instaTab").click();page.locator("#adaptBlog").click();expect(page.locator("#requestAdapt")).to_be_disabled();assert not ai;page.locator("#closeModal").click()
   page.locator("#adaptBlog").click();page.locator("#adaptLanguage").select_option("en");page.locator("#adaptSourceChecked").check();page.locator("#requestAdapt").click();expect(page.locator("#applyAdapt")).to_be_enabled();assert page.evaluate("draft.instagram")=="기존 인스타그램 원고";page.get_by_role("button",name="기존 글 유지 · 닫기",exact=True).click();assert page.evaluate("draft.instagram")=="기존 인스타그램 원고"
   page.locator("#adaptBlog").click();page.locator("#adaptLanguage").select_option("en");page.locator("#adaptSourceChecked").check();page.locator("#requestAdapt").click();expect(page.locator("#applyAdapt")).to_be_enabled();page.locator("#applyAdapt").click();assert page.evaluate("draft.instagram")=="The cream on this latte had a lovely nutty taste.";assert page.evaluate("draft.platform_languages.instagram")=="en";assert page.evaluate("draft.blog")==body;assert page.evaluate("draft.tistory")=="다른 블로그 글";assert page.evaluate("ChannelUI.selected('instagram')")==[ids[2],ids[1],ids[0]];page.locator("#undoGeneration").click();assert page.evaluate("draft.instagram")=="기존 인스타그램 원고";assert page.evaluate("!draft.channel_origins.instagram")
   assert all("threads" not in request and "images" not in request for request in ai);assert ai[-1]["source"]["platform"]=="naver"
   # Number regression, free manual repair, and a changed source blocking a late apply.
   mode["value"]="bad";page.locator("#adaptBlog").click();page.locator("#adaptLanguage").select_option("ko");page.locator("#adaptSourceChecked").check();page.locator("#requestAdapt").click();expect(page.locator("#adaptFeedback")).to_contain_text("숫자");expect(page.locator("#applyAdapt")).to_be_disabled();count=len(ai);page.locator("#adaptCandidate").fill("라떼 2잔을 마셨어요.");expect(page.locator("#applyAdapt")).to_be_enabled();assert len(ai)==count;page.evaluate("value=>{draft.blog+=value;}","\n직접 추가한 문장.");page.locator("#applyAdapt").click();expect(page.locator("#adaptFeedback")).to_contain_text("바뀌었어요");page.locator("#closeModal").click()
   mode["value"]="waiting";old=page.evaluate("draft.instagram");page.locator("#adaptBlog").click();page.locator("#adaptSourceChecked").check();page.locator("#requestAdapt").click();expect(page.locator("#modal .refine-progress")).to_be_visible();page.locator("#closeModal").click();page.wait_for_function("()=>busy===false");mode["value"]="good";assert page.evaluate("draft.instagram")==old
   # A first proposal into an empty channel is reversible; excessive length is repairable without another AI request.
   page.evaluate("draft.threads=''");mode["value"]="long";page.locator("#adaptBlog").click();page.locator("#adaptTarget").select_option("threads");page.locator("#adaptLanguage").select_option("ko");page.locator("#adaptSourceChecked").check();page.locator("#requestAdapt").click();expect(page.locator("#adaptFeedback")).to_contain_text("500");expect(page.locator("#adaptCandidate")).to_have_value("x"*510);expect(page.locator("#applyAdapt")).to_be_disabled();count=len(ai);page.locator("#adaptCandidate").fill("크림이 고소하더라.");expect(page.locator("#applyAdapt")).to_be_enabled();assert len(ai)==count;page.locator("#applyAdapt").click();assert page.evaluate("draft.threads")=="크림이 고소하더라.";page.locator("#undoGeneration").click();assert page.evaluate("draft.threads")=="";expect(page.locator("#platformEmpty")).to_be_visible();page.locator("#instaTab").click();mode["value"]="good"
   page.locator("#saveWorkspace").click();expect(page.locator("#saveState")).to_have_text("저장 완료")
   for theme in ("light","dark"):
    page.evaluate("t=>document.documentElement.dataset.theme=t",theme)
    for width in (320,390,768,1440):
     page.set_viewport_size({"width":width,"height":1050});assert page.evaluate("document.documentElement.scrollWidth<=innerWidth"),(theme,width)
    page.screenshot(path=str(ROOT/("data/qa/channels-"+theme+".png")),full_page=True)
   page.locator("#adaptBlog").click();page.locator("#adaptSourceChecked").check();page.locator("#requestAdapt").click();expect(page.locator("#applyAdapt")).to_be_enabled();page.screenshot(path=str(ROOT/"data/qa/channel-adapt-dark.png"),full_page=True)
   assert not errors,errors;browser.close();print("Channels passed: independent photos/order/first image/crops, exact private preview with no files, undo/redo, save/reopen, Threads text-only, prepared-pool isolation, explicit source review, EN adaptation proposal/cancel/apply/undo, free repair, stale source/cancel safety, themes/mobile. No real AI or SNS calls.")
 finally:process.terminate();process.wait(timeout=10)
