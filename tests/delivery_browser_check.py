"""End-to-end final review, explicit cancellation and saved-revision conflicts; no SNS calls."""
import io,json,os,subprocess,sys,tempfile,time,urllib.request
from pathlib import Path
from PIL import Image
from playwright.sync_api import sync_playwright,expect
ROOT=Path(__file__).resolve().parents[1]
with tempfile.TemporaryDirectory(prefix='mellow-delivery-') as folder:
 process=subprocess.Popen([sys.executable,str(ROOT/'app.py')],cwd=ROOT,env={**os.environ,'PORT':'8898','STUDIO_DATA_DIR':folder,'OPENAI_API_KEY':'','NAVER_BLOG_ID':'sample-blog','INSTAGRAM_ACCESS_TOKEN':'','THREADS_ACCESS_TOKEN':''},stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
 try:
  for _ in range(80):
   try:urllib.request.urlopen('http://127.0.0.1:8898/api/status',timeout=1).close();break
   except Exception:time.sleep(.2)
  with sync_playwright() as p:
   browser=p.chromium.launch(headless=True);page=browser.new_page(viewport={'width':1440,'height':1100},reduced_motion='reduce');errors=[];public=[];handoffs=[]
   page.on('pageerror',lambda e:errors.append(str(e)));page.on('dialog',lambda d:d.accept())
   def status(route):
    response=route.fetch();data=response.json();data.update(instagram=True,threads=True);data['threads_details']={'media_ready':True};route.fulfill(response=response,json=data)
   page.route('**/api/status',status)
   page.on('request',lambda r:handoffs.append(r.post_data_json) if r.method=='POST' and r.url.endswith(('/api/naver/handoff','/api/tistory/handoff')) else None)
   def publish(route):public.append((route.request.url,route.request.post_data_json));route.fulfill(json={'job':'mock-publish-job'})
   page.route('**/api/publish/**',publish);page.route('**/api/jobs/mock-publish-job',lambda r:r.fulfill(json={'state':'done','result':{'media_id':'mock-published'}}))
   page.goto('http://127.0.0.1:8898');page.wait_for_function('()=>!!window.DeliveryUI&&Object.keys(status).length>0')
   for color in ('#b7a5c6','#9cae98'):
    image=io.BytesIO();Image.new('RGB',(600,400),color).save(image,'PNG');page.locator('#photos').set_input_files({'name':'cafe.png','mimeType':'image/png','buffer':image.getvalue()});page.wait_for_timeout(200)
   expect(page.locator('.photo')).to_have_count(2);mids=page.evaluate('draft.images')
   saved=page.evaluate("async()=>await api('/api/drafts',{title:'사진 사이의 작은 이야기',blog:'첫 번째 장면이에요.\\n\\n[[photo:2]]\\n\\n두 번째 장면이에요.\\n\\n[[photo:1]]',tistory_title:'티스토리의 오후',tistory:'티스토리에서 나눌 이야기예요.',instagram:'A quiet little coffee break.',threads:'Just taking a coffee break.',images:draft.images,selective_generation:true,selected_platforms:['naver','instagram','tistory','threads'],platform_languages:{naver:'ko',tistory:'ko',instagram:'en',threads:'en'},channel_media:{instagram:{version:1,images:[draft.images[1]],frame:'square',adjustments:{}},threads:{version:1,images:[],frame:'original',adjustments:{}}}})")
   did=saved['id']
   def load(platform):page.evaluate("async args=>{draft=await api('/api/drafts/'+args[0]);draft.editing_platform=args[1];draft.workspace_step=3;loadDraft();}",[did,platform])
   load('naver');before=page.evaluate('draft.blog');page.locator('#publish').click();expect(page.locator('#modal')).to_have_attribute('data-view','delivery');expect(page.locator('#deliverySummary')).to_contain_text('가운데');expect(page.locator('#deliverySummary')).to_contain_text('나눔바른히피');expect(page.locator('#deliveryTarget')).to_have_text('https://blog.naver.com/sample-blog');assert page.locator('.delivery-photos li').evaluate_all('ns=>ns.map(n=>n.dataset.photoId)')==[mids[1],mids[0]]
   page.locator('#deliveryCancel').click();page.wait_for_function('()=>!busy');assert not handoffs and not public and page.evaluate('draft.blog')==before
   page.locator('#publish').click();expect(page.locator('#deliveryConfirm')).to_be_visible();expect(page.locator('#deliveryConfirm')).to_be_enabled();page.keyboard.press('Escape');page.wait_for_function('()=>!busy');assert not handoffs and not public
   # An update from another writer after the modal opened is rejected before handoff.
   page.locator('#publish').click();expect(page.locator('#deliveryConfirm')).to_be_visible();expect(page.locator('#deliveryConfirm')).to_be_enabled();page.evaluate("async()=>{const other=await api('/api/drafts/'+draft.id);await api('/api/drafts',{...other,blog:'다른 창에서 새로 저장한 원고',blog_documents:{},editing_platform:'naver'});}");page.locator('#deliveryConfirm').click();expect(page.locator('#jobProgress')).to_contain_text('다른 창에서 원고가 바뀌어');page.wait_for_function('()=>!busy');assert page.evaluate('draft.blog')==before;assert len(handoffs)==1 and 'updated' in handoffs[0];assert page.evaluate("document.getElementById('saveConflict').hidden") is False
   # The final panel blocks a photo failure and offers a way back, without issuing a ticket.
   load('naver')
   def unavailable(route):
    response=route.fetch();data=response.json();data['ready']=False;data['photos'][0]['available']=False;data['checks']=[{'level':'error','field':'photos','photo_number':1,'message':'1번 사진을 읽을 수 없어요. 사진을 다시 선택해 주세요.'}];route.fulfill(response=response,json=data)
   page.route('**/api/delivery/preview',unavailable);page.locator('#publish').click();expect(page.locator('#deliveryConfirm')).to_be_disabled();expect(page.locator('#deliveryChecks')).to_contain_text('1번 사진');page.locator('#deliveryCancel').click();page.wait_for_function('()=>!busy');assert len(handoffs)==1;page.unroute('**/api/delivery/preview')
   # A new final confirmation, not cancellation, creates the blog ticket. No editor is remotely operated.
   page.locator('#publish').click();page.locator('#deliveryConfirm').click();expect(page.locator('#modalTitle')).to_contain_text('전달');page.wait_for_function('()=>!busy');assert len(handoffs)==2;page.locator('#closeModal').click()
   load('tistory');page.locator('#tistoryUrl').evaluate('n=>{for(let p=n.parentElement;p;p=p.parentElement)if(p.tagName==="DETAILS")p.open=true;}');page.locator('#tistoryUrl').fill('https://sample.tistory.com');page.locator('#publish').click();expect(page.locator('#deliveryTarget')).to_have_text('https://sample.tistory.com/manage/newpost/');expect(page.locator('.delivery-text')).to_contain_text('티스토리에서');page.locator('#deliveryCancel').click();page.wait_for_function('()=>!busy');assert len(handoffs)==2
   load('instagram');page.locator('#publish').click();expect(page.locator('#deliverySummary')).to_contain_text('1장');expect(page.locator('.delivery-text')).to_contain_text('A quiet little');assert page.locator('.delivery-photos li').evaluate_all('ns=>ns.map(n=>n.dataset.photoId)')==[mids[1]];page.locator('#deliveryCancel').click();page.wait_for_function('()=>!busy');assert not public
   page.locator('#publish').click();page.locator('#deliveryConfirm').click();page.wait_for_function('()=>!busy');assert len(public)==1 and public[0][1]['updated']>0
   load('threads');page.locator('#publish').click();expect(page.locator('#deliverySummary')).to_contain_text('0장');expect(page.locator('.delivery-photos')).to_have_count(0)
   qa=ROOT/'data/qa';qa.mkdir(parents=True,exist_ok=True)
   for theme,width in [('light',1440),('dark',390)]:
    page.set_viewport_size({'width':width,'height':1000});page.evaluate('theme=>document.documentElement.dataset.theme=theme',theme);assert page.evaluate('document.documentElement.scrollWidth<=innerWidth');assert page.locator('#modal').evaluate('n=>n.scrollWidth<=n.clientWidth');page.locator('#modal').screenshot(path=str(qa/('delivery-'+theme+'.png')))
   page.locator('#deliveryConfirm').click();page.wait_for_function('()=>!busy');assert len(public)==2 and public[-1][1]['with_images'] is False and public[-1][1]['updated']>0
   assert not errors,errors;browser.close();print('Delivery passed: four-channel final previews, selected stable photo order, title/language/font/alignment/address, cancel/Escape without handoff or publication, stale revision rejection, unreadable photo gate, explicit blog ticket, IG/Threads confirmation and version payload, text-only Threads, light/dark/mobile. SNS calls mocked; no AI, real publication or public tunnel.')
 finally:process.terminate();process.wait(timeout=10)
