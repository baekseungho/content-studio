"""Long modal content remains readable, scrollable and actionable at narrow/short sizes."""
import io,os,subprocess,sys,tempfile,time,urllib.request
from pathlib import Path
from PIL import Image
from playwright.sync_api import sync_playwright,expect
ROOT=Path(__file__).resolve().parents[1]
with tempfile.TemporaryDirectory(prefix='mellow-modal-layout-') as folder:
 process=subprocess.Popen([sys.executable,str(ROOT/'app.py')],cwd=ROOT,env={**os.environ,'PORT':'8900','STUDIO_DATA_DIR':folder,'OPENAI_API_KEY':'','NAVER_BLOG_ID':'fixture','INSTAGRAM_ACCESS_TOKEN':'','THREADS_ACCESS_TOKEN':''},stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
 try:
  for _ in range(80):
   try:urllib.request.urlopen('http://127.0.0.1:8900/api/status',timeout=1).close();break
   except Exception:time.sleep(.2)
  with sync_playwright() as p:
   browser=p.chromium.launch(headless=True);page=browser.new_page(viewport={'width':1440,'height':1050},reduced_motion='reduce');errors=[];paid=[]
   page.on('pageerror',lambda e:errors.append(str(e)));page.on('dialog',lambda d:d.accept())
   for path in ('**/api/generate','**/api/writing/refine','**/api/channel/adapt','**/api/publish/**','**/api/media/connect'):page.route(path,lambda r:(paid.append(r.request.url),r.abort()))
   page.goto('http://127.0.0.1:8900');page.wait_for_function('()=>!!window.PublicationUI&&!!window.DeliveryUI&&Object.keys(status).length>0')
   for index,color in enumerate(('#a7b59e','#b8a6c9','#d4b79a','#94b8bd','#d4b3b8')):
    image=io.BytesIO();Image.new('RGB',(480,320),color).save(image,'PNG');page.locator('#photos').set_input_files({'name':'moment.png','mimeType':'image/png','buffer':image.getvalue()});expect(page.locator('.photo')).to_have_count(index+1)
   text='식사 또는 이용권을 제공받아 작성한 글입니다.\n\n'+('카페에서 천천히 보낸 오후예요. 창가 자리에 앉아 고소한 라떼를 마셨어요. 잠깐 쉬면서 사진도 남겼어요.\n\n'*20)
   saved=page.evaluate("async text=>await api('/api/drafts',{title:'대구 카페에서 사진과 함께 남긴 오후의 이야기',blog:text,images:draft.images,instagram:'A slow afternoon with a latte.',selective_generation:true,selected_platforms:['naver','instagram'],editing_platform:'naver',template:'reference'})",text);did=saved['id'];page.evaluate('d=>{draft=d;loadDraft();}',saved);before=page.evaluate('JSON.stringify({blog:draft.blog,images:draft.images,instagram:draft.instagram})')
   page.evaluate('()=>{void DeliveryUI.confirm("naver").then(v=>window.layoutConfirmed=v);}')
   expect(page.locator('#deliveryConfirm')).to_be_visible();qa=ROOT/'data/qa';qa.mkdir(parents=True,exist_ok=True)
   for theme in ('light','dark'):
    page.evaluate('t=>document.documentElement.dataset.theme=t',theme)
    for width,height in ((1440,1050),(1280,720),(768,900),(390,844),(320,740)):
     page.set_viewport_size({'width':width,'height':height});page.locator('.modal-scroll-region').evaluate('n=>n.scrollTop=0');page.wait_for_timeout(30)
     result=page.evaluate("""()=>{const q=s=>document.querySelector(s),rect=n=>{const r=n.getBoundingClientRect();return {left:r.left,right:r.right,top:r.top,bottom:r.bottom};},modal=q('#modal'),body=q('#modalBody'),region=q('.modal-scroll-region'),article=q('.delivery-text'),preview=q('.delivery-preview'),summary=preview.querySelector('summary'),actions=q('.delivery-actions');return {modal:rect(modal),region:rect(region),actions:rect(actions),preview:rect(preview),summary:rect(summary),close:rect(q('#closeModal')),regionScrolls:region.scrollHeight>region.clientHeight,bodyOverflow:body.scrollHeight-body.clientHeight,articleOverflow:article.scrollHeight-article.clientHeight,horizontal:region.scrollWidth-region.clientWidth};}""")
     assert result['regionScrolls'],(theme,width,result);assert result['bodyOverflow']<=2 and result['articleOverflow']<=2,(theme,width,result);assert result['horizontal']<=2,(theme,width,result)
     assert result['actions']['top']>=result['region']['bottom']-1,(theme,width,result);assert result['summary']['left']-result['preview']['left']>=15,(theme,width,result)
     assert result['modal']['bottom']<=height-10 and result['modal']['top']>=10,(theme,width,result)
     page.locator('.modal-scroll-region').evaluate('n=>n.scrollTop=n.scrollHeight');page.wait_for_timeout(30)
     assert page.locator('.delivery-photos li').last.evaluate("n=>n.getBoundingClientRect().bottom<=document.querySelector('.modal-scroll-region').getBoundingClientRect().bottom-10"),(theme,width)
     for name in ('deliveryCancel','deliveryConfirm'):assert page.locator('#'+name).evaluate("n=>{const r=n.getBoundingClientRect(),m=document.getElementById('modal').getBoundingClientRect();return r.bottom<=m.bottom-14&&r.left>=m.left+14&&r.right<=m.right-14;}"),(theme,width,name)
     if width in (1440,390):
      page.locator('.modal-scroll-region').evaluate('n=>n.scrollTop=0');page.locator('#modal').screenshot(path=str(qa/('modal-delivery-'+theme+'-'+str(width)+'.png')))
   page.locator('#deliveryCancel').click();page.wait_for_function('()=>window.layoutConfirmed===false');assert before==page.evaluate('JSON.stringify({blog:draft.blog,images:draft.images,instagram:draft.instagram})')
   # Exercise actual modal builders without requesting suggestions, publishing or saving settings.
   cases=[('settings',"openSettings()"),('library',"void LibraryUI.open()"),('kits',"void KitsUI.open()"),('kit-save',"KitsUI.saveCurrent()"),('help',"WorkspaceHelp.open()"),('voice',"$('manageVoice').click()"),('record',"PublicationUI.openRecord()"),('refine',"WritingUI.openBlock(BlockWorkspace.ensure().blocks.find(b=>b.type==='paragraph'))"),('adapt',"void ChannelUI.openAdapt()")]
   for name,action in cases:
    page.set_viewport_size({'width':1440,'height':1050});page.evaluate('a=>{'+ 'eval(a)' +';}',action);expect(page.locator('#modal')).to_be_visible()
    for theme in ('light','dark'):
     page.evaluate('t=>document.documentElement.dataset.theme=t',theme)
     for width in (1440,768,390,320):
      page.set_viewport_size({'width':width,'height':900});page.wait_for_timeout(25)
      assert page.locator('#modalBody').evaluate('n=>n.scrollWidth<=n.clientWidth+2'),(name,theme,width)
      assert page.locator('#modal').evaluate('n=>{const r=n.getBoundingClientRect();return r.left>=10&&r.right<=innerWidth-10&&r.top>=10&&r.bottom<=innerHeight-10;}'),(name,theme,width)
      assert page.locator('#modalBody').evaluate('n=>{const sc=n.querySelector(".modal-scroll-region")||n,r=sc.getBoundingClientRect(),h=document.querySelector(".modal-heading").getBoundingClientRect();return r.top>=h.bottom+6&&sc.scrollWidth<=sc.clientWidth+2;}'),(name,theme,width)
      page.locator('#modalBody').evaluate('n=>{const sc=n.querySelector(".modal-scroll-region")||n;sc.scrollTop=sc.scrollHeight;}')
      if page.locator('.modal-action-bar').count():assert page.locator('.modal-action-bar').evaluate('n=>n.getBoundingClientRect().top>=document.querySelector(".modal-scroll-region").getBoundingClientRect().bottom-1'),(name,theme,width)
      assert page.locator('#closeModal').evaluate('n=>{const r=n.getBoundingClientRect(),m=document.getElementById("modal").getBoundingClientRect();return r.top>=m.top+8&&r.right<=m.right-8;}'),(name,theme,width)
     if name in ('settings','kit-save','refine','help'):
      page.locator('#modalBody').evaluate('n=>{const sc=n.querySelector(".modal-scroll-region")||n;sc.scrollTop=0;}');page.locator('#modal').screenshot(path=str(qa/('modal-'+name+'-'+theme+'-mobile.png')))
    if name=='settings':
     rect=page.locator('#modal').bounding_box();heading=page.locator('.modal-heading').bounding_box();page.mouse.click(rect['x']+rect['width']-3,heading['y']+heading['height']+16);expect(page.locator('#modal')).to_be_visible();page.mouse.click(2,2);expect(page.locator('#modal')).not_to_be_visible()
    else:page.locator('#closeModal').click()
    page.wait_for_function('()=>!busy')
   assert not paid,paid;assert not errors,errors;assert before==page.evaluate('JSON.stringify({blog:draft.blog,images:draft.images,instagram:draft.instagram})');browser.close();print('Modal layout passed: one delivery scroller, unobscured footer and final photo, inset scrollbars/panels, long article and five photos, 320-1440px and short viewport, light/dark, settings/library/kits/help/record/refine/adapt builders, interior whitespace vs backdrop clicks, preserved manuscripts. No AI or publication.')
 finally:process.terminate();process.wait(timeout=10)
