"""네이버 입력 프록시에서 이모지 정규화·지연 렌더·문단 재생성을 재현한다."""
import base64
import io
from pathlib import Path
import unittest
from PIL import Image
from playwright.sync_api import sync_playwright
import test_extension

PROXY = r"""()=>{
 const inner=document.querySelector('iframe').contentDocument;
 const models=new WeakMap(),owners=new Map();let serial=0;
 window.mixedEmojiDrops=0;window.bodyInsertCalls=0;window.formatBeforeText=false;
 const norm=value=>value.normalize('NFC').replace(/[\s\u200b\uFE0E\uFE0F]/g,'');
 const allBody=()=>[...document.querySelectorAll('.se-section-text')].map(el=>el.textContent).join('');
 const model=section=>{
  if(!models.has(section)){section.dataset.owner=String(++serial);owners.set(String(serial),section);models.set(section,[{text:''}]);}
  return models.get(section);
 };
 const render=section=>{
  const lines=model(section),make=(item,index)=>{
   const p=document.createElement('p');p.className='se-text-paragraph';p.dataset.line=String(index);p.textContent=item.text||'\u200b';
   p.style.fontFamily=item.font||'Arial';p.style.fontSize=(item.size||15)+'px';p.style.textAlign=item.align||'left';return p;
  };
  if(window.splitOutput&&section.matches('.se-section-text')){
   document.querySelectorAll('[data-split="'+section.dataset.owner+'"]').forEach(el=>el.remove());
   section.replaceChildren(make(lines[0],0));let anchor=section;
   for(let i=1;i<lines.length;i++){
    const next=document.createElement('div');next.className='se-section-text';next.dataset.split=section.dataset.owner;next.append(make(lines[i],i));anchor.after(next);anchor=next;
   }
  }else section.replaceChildren(...lines.map(make));
 };
 const focus=()=>{
  inner.body.textContent=window.currentModel[window.currentLine].text;
  inner.body.focus();const range=inner.createRange();range.selectNodeContents(inner.body);range.collapse(false);inner.getSelection().removeAllRanges();inner.getSelection().addRange(range);
 };
 document.addEventListener('pointerdown',event=>{
  let section=event.target.closest('.se-section-documentTitle,.se-section-text');if(!section)return;
  event.stopImmediatePropagation();if(section.dataset.split)section=owners.get(section.dataset.split);
  window.currentSection=section;window.currentModel=model(section);
  window.currentLine=Number(event.target.closest('p')?.dataset.line||0);focus();
 },true);
 inner.body.addEventListener('keydown',event=>{
  if(event.key!=='Enter')return;event.preventDefault();
  window.currentModel.splice(window.currentLine+1,0,{text:''});window.currentLine++;focus();render(window.currentSection);
 },true);
 inner.body.addEventListener('input',event=>{
  event.stopImmediatePropagation();const section=window.currentSection;
  let value=inner.body.textContent;
  // 기존 일괄 입력처럼 이모지와 한글을 한 번에 보내면 글자가 빠지는 편집기를 재현한다.
  if(/\p{Extended_Pictographic}/u.test(event.data||'')&&/[가-힣A-Za-z]/u.test(event.data||'')){
   window.mixedEmojiDrops++;value=value.slice(0,value.length-event.data.length)+(event.data.match(/^\p{Extended_Pictographic}\uFE0F?/u)?.[0]||'');
  }
  if(section.matches('.se-section-text')){
   window.bodyInsertCalls++;
   if(window.truncatePlain)value=value.slice(0,1);
  }
  window.currentModel[window.currentLine].text=value.replace(/\uFE0F/g,'');focus();
  if(window.caretAtStartAfterEmoji&&/\p{Extended_Pictographic}/u.test(event.data||'')){
   const range=inner.createRange();range.selectNodeContents(inner.body);range.collapse(true);inner.getSelection().removeAllRanges();inner.getSelection().addRange(range);
  }
  setTimeout(()=>render(section),35);
 },true);
 const mark=()=>{if(norm(allBody())!==norm(window.expectedBody||''))window.formatBeforeText=true;};
 const set=values=>{Object.assign(window.currentModel[window.currentLine],values);render(window.currentSection);};
 const toolbar=document.createElement('div');toolbar.innerHTML='<button data-name="font-family" class="se-font-family-toolbar-button">서체 변경</button><div id="fonts" hidden><button data-value="nanumbareunhipi">바른히피바른히피</button></div><button data-name="font-size" class="se-font-size-code-toolbar-button">15글자 크기 변경</button><div id="sizes" hidden><button data-value="fs15">1515선택됨</button></div><button data-name="align-drop-down-with-justify" class="se-property-toolbar-drop-down-button se-align-left-toolbar-button">정렬정렬 열기</button><div id="aligns" hidden><button data-name="align-drop-down-with-justify" data-value="center" class="__se-sentry se-toolbar-option-icon-button se-toolbar-option-align-center-button">가운데 정렬</button></div>';
 document.body.prepend(toolbar);
 toolbar.querySelector('[data-name="font-family"]').onclick=()=>{mark();document.querySelector('#fonts').hidden=false;};
 toolbar.querySelector('[data-value="nanumbareunhipi"]').onclick=()=>{set({font:'se-nanumbareunhipi'});document.querySelector('#fonts').hidden=true;};
 toolbar.querySelector('[data-name="font-size"]').onclick=()=>{mark();document.querySelector('#sizes').hidden=false;};
 toolbar.querySelector('[data-value="fs15"]').onclick=()=>{set({size:15});document.querySelector('#sizes').hidden=true;};
 toolbar.querySelector('.se-property-toolbar-drop-down-button').onclick=()=>{mark();document.querySelector('#aligns').hidden=false;};
 toolbar.querySelector('[data-value="center"]').onclick=()=>{set({align:'center'});document.querySelector('#aligns').hidden=true;};
 const input=document.createElement('input');input.type='file';input.accept='image/*';document.body.append(input);
 input.onchange=()=>{
  for(const file of input.files){
   const image=document.createElement('img');image.className='se-image-resource';image.alt=file.name;image.src=URL.createObjectURL(file);
   const box=document.createElement('div');box.className='se-component se-image';box.append(image);
   const next=document.createElement('div');next.className='se-section-text';next.innerHTML='<p class="se-text-paragraph"><br></p>';
   window.currentSection.after(box,next);
  }
 };
}"""

class ProxyStreamingTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.p=sync_playwright().start();cls.browser=cls.p.chromium.launch(headless=True)
  cls.script=Path(__file__).resolve().parents[1]/'chrome-extension/editor.js'
 @classmethod
 def tearDownClass(cls):cls.browser.close();cls.p.stop()
 def setUp(self):
  self.page=self.browser.new_page();test_extension.ExtensionEditorTests.prepare_input_iframe(self);self.page.evaluate(PROXY)
 def tearDown(self):self.page.close()
 def test_emoji_proxy_full_text_three_photos_then_native_format(self):
  body='부산 호텔 다녀왔어요.\n\n♨️ 밤에 즐긴 온천\n[[photo:1]]\n야경도 남겼어요 🌙\n[[photo:2]]\n🌊 객실에서 본 바다\n셀카도 한 장 👩🏻‍💻 🤍\n[[photo:3]]\n마무리까지 잘 남겼어요 ✨'
  expected=body.replace('[[photo:1]]','').replace('[[photo:2]]','').replace('[[photo:3]]','')
  self.page.evaluate('value=>{window.expectedBody=value;window.caretAtStartAfterEmoji=true;}',expected)
  photos=[]
  for i,color in enumerate(('red','green','blue')):
   data=io.BytesIO();Image.new('RGB',(8,8),color).save(data,'JPEG');photos.append({'name':str(i+1)+'.jpg','base64':base64.b64encode(data.getvalue()).decode()})
  result=self.page.evaluate("payload=>editorAction('fill',payload)",{'title':'테스트 후기','body':body,'photos':photos,'format':{'align':'center','font':'나눔바른히피','font_key':'nanumbareunhipi','size':15}})
  self.assertEqual(result['state'],'ready',result)
  self.assertEqual(result['count'],3)
  self.assertTrue(result['formatting']['verified'])
  self.assertFalse(self.page.evaluate('window.formatBeforeText'))
  self.assertEqual(self.page.evaluate('window.mixedEmojiDrops'),0)
  self.assertEqual(self.page.locator('img.se-image-resource').count(),3)
  text=''.join(self.page.locator('.se-section-text').all_text_contents())
  self.assertIn('밤에 즐긴 온천',text);self.assertIn('마무리까지 잘 남겼어요',text)
 def test_recreated_sibling_sections_are_included_in_text_verification(self):
  self.page.evaluate('window.splitOutput=true')
  result=self.page.evaluate("payload=>editorAction('fill',payload)",{'title':'제목','body':'첫 줄\n\n♨️ 밤에 즐긴 온천\n끝까지 입력해요','photos':[]})
  self.assertEqual(result['state'],'ready',result)
  self.assertGreater(self.page.locator('.se-section-text').count(),1)
 def test_truncated_text_stops_without_duplicate_retry_or_photo_upload(self):
  self.page.evaluate('window.truncatePlain=true')
  result=self.page.evaluate("()=>editorAction('fill',{title:'제목',body:'테스트 본문을 온전히 입력해야 해요',photos:[]})")
  self.assertEqual(result['state'],'failed')
  self.assertEqual(self.page.evaluate('window.bodyInsertCalls'),1)
  self.assertEqual(result['count'],0)
  self.assertEqual(result['diagnostics']['textSync']['line'],1)
  self.assertFalse(result['diagnostics']['textSync']['exact'])
