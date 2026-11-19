"""Block editing, legacy import, scoped photos, durable history and handoff parity."""
import io,json,os,subprocess,sys,tempfile,time,urllib.request
from pathlib import Path
from PIL import Image
from playwright.sync_api import sync_playwright,expect
ROOT=Path(__file__).resolve().parents[1]
def photo(name,color):
 b=io.BytesIO();Image.new('RGB',(600,400),color).save(b,'PNG');return {'name':name,'mimeType':'image/png','buffer':b.getvalue()}
with tempfile.TemporaryDirectory(prefix='mellow-blocks-') as folder:
 process=subprocess.Popen([sys.executable,str(ROOT/'app.py')],cwd=ROOT,env={**os.environ,'PORT':'8892','STUDIO_DATA_DIR':folder,'OPENAI_API_KEY':'','INSTAGRAM_ACCESS_TOKEN':'','THREADS_ACCESS_TOKEN':''},stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
 try:
  for _ in range(70):
   try:urllib.request.urlopen('http://127.0.0.1:8892/api/status',timeout=1).close();break
   except Exception:time.sleep(.2)
  with sync_playwright() as p:
   browser=p.chromium.launch(headless=True);page=browser.new_page(viewport={'width':1440,'height':1050},reduced_motion='reduce');errors=[];ai=[]
   page.on('pageerror',lambda e:errors.append(str(e)));page.on('dialog',lambda d:d.accept());page.route('**/api/generate',lambda route:(ai.append(1),route.abort()))
   page.goto('http://127.0.0.1:8892');page.wait_for_function('Object.keys(status).length>0')
   page.locator('#photos').set_input_files([photo('one.png','#c9b8ac'),photo('two.png','#b9c4d1'),photo('three.png','#b5c9bc')]);expect(page.locator('.photo')).to_have_count(3)
   ids=page.evaluate('draft.images.slice()');legacy='첫 번째 이야기예요.\n\n[[photo:1]]\n\n## 창가에서 보낸 오후\n\n두 번째 장면이에요.\n\n[[photo:2]]\n\n마지막 이야기도 남겨요.\n\n[[photo:3]]'
   page.evaluate('arg=>{draft={...fresh(),workspace_step:2,title:"기억하고 싶은 카페",blog:arg.body,tistory_title:"티스토리의 다른 글",tistory:arg.body,instagram:"인스타그램은 그대로",threads:"Threads도 그대로",images:arg.ids,selective_generation:true};loadDraft();}',{'body':legacy,'ids':ids})
   page.locator('.preview-editable').first.click();expect(page.locator('#blockEditor')).to_be_visible();expect(page.locator('#body')).not_to_be_visible();expect(page.locator('.photo-block')).to_have_count(3)
   assert page.evaluate('draft.blog_documents.naver.original.body')==legacy
   first=page.locator('.paragraph-block textarea').first;first.fill('창가 자리에서 여유롭게 보낸 오후예요.\n커피 향이 좋았어요.');assert '커피 향' in page.evaluate('draft.blog')
   first_photo=page.locator('.photo-block').first;first_photo.locator('.block-caption').fill('첫 번째 사진의 설명을 지켜 주세요.');photo_id=first_photo.get_attribute('data-block-id')
   first_photo.get_by_role('button',name='이 문단 위로 이동',exact=True).click();assert page.evaluate('draft.blog_documents.naver.blocks[0].id')==photo_id
   expect(page.locator('.photo-block').first.locator('.block-caption')).to_have_value('첫 번째 사진의 설명을 지켜 주세요.')
   # Real drag-and-drop and the keyboard alternative must update the same document.
   page.locator('.paragraph-block').first.locator('.block-grip').drag_to(page.locator('.photo-block').first, target_position={'x':40,'y':8})
   assert page.evaluate('BlockWorkspace.ensure().blocks[0].type')=='paragraph';page.locator('#blockUndo').click();assert page.evaluate('BlockWorkspace.ensure().blocks[0].id')==photo_id
   page.locator('.photo-block').first.get_by_role('button',name='이 글의 사진 교체',exact=True).click();page.locator('#modalBody input[type=file]').set_input_files(photo('replacement.png','#a79abb'));expect(page.locator('#modal')).not_to_be_visible()
   replaced=page.evaluate('StoryBlocks.photos(draft.blog_documents.naver)');assert replaced[0]!=ids[0] and len(replaced)==3 and page.evaluate('draft.images')==ids
   assert page.evaluate('draft.tistory')==legacy and page.evaluate('draft.instagram')=='인스타그램은 그대로'
   expect(page.locator('.photo-block').first.locator('.block-caption')).to_have_value('첫 번째 사진의 설명을 지켜 주세요.')
   page.locator('.photo-block').first.get_by_role('button',name='이 글에서 사진 빼기',exact=True).click();expect(page.locator('.photo-block')).to_have_count(2);page.locator('#blockUndo').click();expect(page.locator('.photo-block')).to_have_count(3);page.locator('#blockRedo').click();expect(page.locator('.photo-block')).to_have_count(2);page.locator('#blockUndo').click()
   page.locator('#blockAddText').click();last=page.locator('.paragraph-block textarea').last;last.fill('나눌 문단이에요. 이어지는 이야기예요.');last.evaluate('el=>el.setSelectionRange(10,10)');last.press('Control+Enter');assert page.locator('.paragraph-block').count()==5;page.locator('#blockUndo').click();last=page.locator('.paragraph-block textarea').last;last.fill('새 문단도 쉽게 남겨요. <script>window.bad=true</script>');assert page.evaluate('window.bad===undefined')
   last.press('Control+z');assert page.locator('.paragraph-block textarea').last.input_value()!='새 문단도 쉽게 남겨요. <script>window.bad=true</script>';page.locator('.paragraph-block textarea').last.press('Control+Shift+z');expect(page.locator('.paragraph-block textarea').last).to_have_value('새 문단도 쉽게 남겨요. <script>window.bad=true</script>')
   page.locator('.paragraph-block').last.get_by_role('button',name='소제목으로 바꾸기',exact=True).click();assert '## 새 문단' in page.evaluate('draft.blog')
   # Handoff and export use the exact document order, not prepared-photo order.
   page.locator('#saveWorkspace').click();expect(page.locator('#saveState')).to_have_text('저장 완료');did=page.evaluate('draft.id');doc=page.evaluate('draft.blog_documents.naver');expected=page.evaluate('StoryBlocks.photos(draft.blog_documents.naver)')
   saved=page.evaluate('async id=>await api("/api/drafts/"+id)',did);assert saved['blog_documents']['naver']['source']==saved['blog'];assert saved['blog_documents']['naver']['blocks'][0]['image_id']==expected[0]
   export=page.request.get('http://127.0.0.1:8892/export/'+did).text();assert '&lt;script&gt;' in export and '<script>window.bad' not in export
   page.evaluate('goWorkspace(1)');page.get_by_role('button',name='사진 뒤로 이동',exact=True).first.click();assert page.evaluate('StoryBlocks.photos(draft.blog_documents.naver)')==expected
   page.evaluate('goWorkspace(2)');page.locator('#tistoryTab').click();expect(page.locator('#preview')).to_contain_text('두 번째 장면');assert page.evaluate('StoryBlocks.photos(BlockWorkspace.ensure())')==ids
   page.locator('#blogTab').click();page.locator('#saveWorkspace').click();expect(page.locator('#saveState')).to_have_text('저장 완료')
   page.evaluate('async id=>{draft=await api("/api/drafts/"+id);loadDraft();}',did);page.locator('#previewToggle').click();expect(page.locator('#blockUndo')).to_be_enabled();assert page.evaluate('StoryBlocks.photos(BlockWorkspace.ensure())')==expected
   page.locator('#blockUndo').click();page.locator('#blockRedo').click();assert page.evaluate('StoryBlocks.photos(BlockWorkspace.ensure())')==expected
   for theme in ('light','dark'):
    page.evaluate('t=>document.documentElement.dataset.theme=t',theme)
    for width in (320,390,768,1440):
     page.set_viewport_size({'width':width,'height':1050});assert page.evaluate('document.documentElement.scrollWidth<=innerWidth'),(theme,width)
    page.screenshot(path=str(ROOT/('data/qa/blocks-'+theme+'.png')),full_page=True)
   # A length-only revision must not restore photos the user removed from this blog.
   page.locator('.photo-block').last.get_by_role('button',name='이 글에서 사진 빼기',exact=True).click();selected=page.evaluate('StoryBlocks.photos(BlockWorkspace.ensure())');assert len(selected)==2
   revisions=[]
   page.route('**/api/blog/expand',lambda route:(revisions.append(route.request.post_data_json),route.fulfill(json={'job':'block-length'})))
   page.route('**/api/jobs/block-length',lambda route:route.fulfill(json={'state':'done','result':{'title':revisions[-1]['seed']['title'],'blog':revisions[-1]['seed']['body']+'\n\n확인한 경험을 한 문단 더 남겨요.','checks':[]}}))
   page.evaluate('async()=>{$("prompt").value="직접 확인한 경험만 보완해 주세요.";await generateForPlatforms(["naver"],true,true);}')
   assert revisions[0]['images']==selected and page.evaluate('StoryBlocks.photos(BlockWorkspace.ensure())')==selected
   assert page.evaluate('draft.images')!=selected and page.evaluate('BlockWorkspace.ensure().blocks.find(b=>b.type==="photo").caption')=='첫 번째 사진의 설명을 지켜 주세요.'
   assert not errors,errors;assert not ai;browser.close();print('Blocks passed: lossless legacy source, text/headings, scoped replacement/removal, stable IDs, captions, undo/redo across save/reopen, export escaping, channel isolation, themes/mobile; no real AI or SNS calls.')
 finally:process.terminate();process.wait(timeout=10)
