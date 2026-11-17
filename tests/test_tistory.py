import base64
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from playwright.sync_api import sync_playwright
import app
from extension_bridge import ExtensionBridge
from naver_guard import NaverGuard

FIXTURE="""<!doctype html><input id="post-title-inp"><div id="content" contenteditable="true"></div><input type="file" accept="image/*"><script>
const body=document.querySelector('#content');let anchor=null;
window.tinymce={get:()=>({getBody:()=>body,getWin:()=>window,focus:()=>{},save:()=>{},nodeChanged:()=>{},
 selection:{getBookmark:()=>null,moveToBookmark:()=>{},select:el=>anchor=el,collapse:()=>{}},
 insertContent:html=>{const template=document.createElement('template');template.innerHTML=html;const nodes=[...template.content.childNodes];if(anchor)anchor.after(...nodes);else body.append(...nodes);anchor=nodes.at(-1);}})};
document.querySelector('[type=file]').onchange=()=>{
 const img=new Image();img.src='https://media.test/photo.jpg';
 if(anchor)anchor.after(img);else body.append(img);anchor=img;
};</script>"""
class TistoryTests(unittest.TestCase):
 def test_writer_urls_reject_non_blog_targets(self):
  self.assertEqual(app.tistory_writer_url('https://my-blog.tistory.com/'),'https://my-blog.tistory.com/manage/newpost/')
  for value in ['http://my.tistory.com','https://tistory.com','https://my.tistory.com.evil.com','https://user@my.tistory.com','https://my.tistory.com/manage','https://my.tistory.com/?x=1','https://notice.tistory.com']:
   with self.subTest(value=value),self.assertRaises((app.Problem,ValueError)):app.tistory_writer_url(value)
 def test_channel_guards_and_codes_are_independent(self):
  with tempfile.TemporaryDirectory() as folder:
   root=Path(folder);naver=ExtensionBridge(root,NaverGuard(root/'naver.json'));tistory=ExtensionBridge(root,NaverGuard(root/'tistory.json'),channel='tistory')
   draft={'id':'a'*32,'title':'제목','blog':'본문','images':[]}
   first=naver.redeem(naver.create(draft)['code']);naver.report(first['report_token'],'ready',0)
   code=tistory.create(draft)['code'];second=tistory.redeem(code)
   tistory.report(second['report_token'],'ready',0,{'stage':'티스토리 확인'})
   self.assertTrue((root/'tistory-extension-diagnostics.json').exists())
 def test_transient_picker_input_event_and_prototype_restoration(self):
  with sync_playwright() as p:
   browser=p.chromium.launch(headless=True);page=browser.new_page();page.set_content(FIXTURE)
   page.route('https://media.test/**',lambda route:route.fulfill(content_type='image/png',body=base64.b64decode('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+jRZkAAAAASUVORK5CYII=')))
   page.evaluate("""()=>{
    document.querySelector('[type=file]').remove();window.originalClick=HTMLInputElement.prototype.click;
    const attach=document.createElement('button');attach.textContent='첨부';document.body.append(attach);
    attach.onclick=()=>{
     const photo=document.createElement('button');photo.textContent='사진';document.body.append(photo);
     photo.onclick=()=>{
      const input=document.createElement('input');input.type='file';document.body.append(input);
      input.addEventListener('input',()=>{
       window.fileDelivered=input.files.length;
       const img=new Image();img.src='https://media.test/photo.jpg';body.append(img);
      });
      input.click();input.remove();photo.remove();
     };
    };
   }""")
   page.add_script_tag(path=str(Path(__file__).resolve().parents[1]/'chrome-extension/tistory.js'))
   result=page.evaluate("payload=>tistoryAction('fill',payload)",{'title':'사진 테스트','body':'사진 앞\n\n[[photo:1]]\n\n사진 뒤','photos':[{'name':'1.jpg','base64':'aW1hZ2U='}],'format':{'align':'center'}})
   self.assertEqual(result['state'],'ready',result)
   self.assertEqual(page.evaluate('window.fileDelivered'),1)
   self.assertEqual(page.locator('[type=file]').count(),0)
   self.assertTrue(page.evaluate('HTMLInputElement.prototype.click===window.originalClick'))
   browser.close()
 def test_editor_text_photo_order_and_no_overwrite(self):
  with sync_playwright() as p:
   browser=p.chromium.launch(headless=True);page=browser.new_page();page.set_content(FIXTURE)
   page.route('https://media.test/**',lambda route:route.fulfill(content_type='image/png',body=base64.b64decode('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+jRZkAAAAASUVORK5CYII=')))
   page.add_script_tag(path=str(Path(__file__).resolve().parents[1]/'chrome-extension/tistory.js'))
   self.assertTrue(page.evaluate("()=>tistoryAction('probe')")['eligible'])
   result=page.evaluate("payload=>tistoryAction('fill',payload)",{'title':'여행 후기','body':'도입 이야기\n\n[[photo:1]]\n\n## 사진 뒤 이야기\n마무리 🤍','photos':[{'name':'1.jpg','base64':'aW1hZ2U='}],'format':{'align':'center'}})
   self.assertEqual(result['state'],'ready',result);self.assertEqual(result['count'],1)
   self.assertEqual(result['formatting']['expected']['font'],'나눔명조')
   self.assertIn('Nanum Myeongjo',page.locator('#content p').first.get_attribute('style'))
   self.assertEqual(page.locator('#content img').count(),1)
   order=page.locator('#content').evaluate("el=>[...el.children].map(n=>n.tagName)")
   self.assertLess(order.index('IMG'),order.index('H3'))
   second=page.evaluate("()=>tistoryAction('fill',{title:'덮어쓰기',body:'안됨',photos:[]})")
   self.assertEqual(second['state'],'failed');self.assertEqual(page.locator('#post-title-inp').input_value(),'여행 후기')
   browser.close()

 def test_mixed_span_font_is_not_reported_success(self):
  with sync_playwright() as p:
   browser=p.chromium.launch(headless=True);page=browser.new_page();page.set_content(FIXTURE)
   page.evaluate("""()=>{
    const original=window.tinymce.get;
    window.tinymce.get=()=>{const editor=original();const insert=editor.insertContent;
     editor.insertContent=html=>{insert(html);body.querySelectorAll('p').forEach(el=>{el.innerHTML='<span style="font-family:Arial">'+el.textContent+'</span>';});};return editor;};
   }""")
   page.add_script_tag(path=str(Path(__file__).resolve().parents[1]/'chrome-extension/tistory.js'))
   result=page.evaluate("()=>tistoryAction('fill',{title:'제목',body:'보존할 문장',photos:[],format:{align:'center'}})")
   self.assertEqual(result['state'],'partial',result)
   self.assertFalse(result['formatting']['font'])
   browser.close()
 def test_automatic_photo_caption_does_not_hide_successful_body_input(self):
  with sync_playwright() as p:
   browser=p.chromium.launch(headless=True);page=browser.new_page();page.set_content(FIXTURE)
   page.route('https://media.test/**',lambda route:route.fulfill(content_type='image/png',body=base64.b64decode('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+jRZkAAAAASUVORK5CYII=')))
   page.evaluate("""()=>document.querySelector('[type=file]').addEventListener('change',()=>{
    const image=body.querySelector('img');const figure=document.createElement('figure');image.replaceWith(figure);figure.append(image);
    const caption=document.createElement('figcaption');caption.innerHTML='<p style="font-family:Arial;font-size:12px">사진 파일 설명</p>';figure.append(caption);
   })""")
   page.add_script_tag(path=str(Path(__file__).resolve().parents[1]/'chrome-extension/tistory.js'))
   result=page.evaluate("payload=>tistoryAction('fill',payload)",{'title':'제목','body':'사진 앞\n\n[[photo:1]]\n\n사진 뒤','photos':[{'name':'1.jpg','base64':'aW1hZ2U='}],'format':{'align':'center'}})
   self.assertEqual(result['state'],'ready',result)
   browser.close()
