import base64,io,json,tempfile,unittest
from pathlib import Path
from PIL import Image
from playwright.sync_api import sync_playwright
from extension_bridge import ExtensionBridge,HandoffError
from naver_guard import NaverGuard
from test_extension import FIXTURE
from test_tistory import FIXTURE as TISTORY
ROOT=Path(__file__).resolve().parents[1]

class TransferReceiptTests(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name);self.guard=NaverGuard(self.root/'guard.json');self.bridge=ExtensionBridge(self.root,self.guard);self.mid='a'*32;(self.root/(self.mid+'.jpg')).write_bytes(b'image');self.draft={'id':'b'*32,'title':'제목','blog':'본문','images':[self.mid]}
 def tearDown(self):self.temp.cleanup()
 def test_lost_report_response_can_be_retried_without_repeating_input(self):
  payload=self.bridge.redeem(self.bridge.create(self.draft)['code']);token=payload['report_token']
  self.assertTrue(self.bridge.report(token,'ready',1)['recorded']);again=self.bridge.report(token,'ready',1)
  self.assertTrue(again['already_recorded']);self.assertEqual(self.guard.read()['completed'],[self.draft['id']]);self.assertEqual(self.guard.status()['attempts_24h'],1)
  with self.assertRaises(HandoffError):self.bridge.report(token,'failed',0)
  with self.assertRaises(HandoffError):self.bridge.report(token,'ready',True)
  self.assertIn(self.draft['id'],self.guard.read()['completed'])
 def test_inflight_content_cannot_get_a_second_ticket_even_with_repeat_confirmed(self):
  payload=self.bridge.redeem(self.bridge.create(self.draft)['code'])
  with self.assertRaisesRegex(HandoffError,'결과 기록'):self.bridge.create(self.draft,allow_repeat=True)
  self.bridge.report(payload['report_token'],'failed',0)
  self.assertIn('code',self.bridge.create(self.draft,allow_repeat=True))
 def test_missing_photo_does_not_consume_code_or_cooldown(self):
  code=self.bridge.create(self.draft)['code'];file=self.root/(self.mid+'.jpg');file.unlink()
  with self.assertRaises(HandoffError):self.bridge.redeem(code)
  self.assertIn(code,self.bridge.tickets);self.assertEqual(self.guard.status()['attempts_24h'],0)
  file.write_bytes(b'image');self.assertIn('body',self.bridge.redeem(code))

 def test_readonly_inspection_identifies_target_without_consuming_the_code(self):
  writer='https://blog.naver.com/expected?Redirect=Write&';code=self.bridge.create(self.draft,writer_url=writer)['code']
  info=self.bridge.inspect(code);self.assertEqual(info['writer_url'],writer);self.assertEqual(info['photo_count'],1)
  self.assertNotIn('body',info);self.assertNotIn('title',info);self.assertIn(code,self.bridge.tickets);self.assertEqual(self.guard.status()['attempts_24h'],0)

class TransferEditorTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):cls.p=sync_playwright().start();cls.browser=cls.p.chromium.launch(headless=True)
 @classmethod
 def tearDownClass(cls):cls.browser.close();cls.p.stop()
 def setUp(self):self.page=self.browser.new_page()
 def tearDown(self):self.page.close()
 def test_naver_detects_loss_of_previously_confirmed_text_after_photo_upload(self):
  self.page.set_content(FIXTURE);self.page.evaluate("()=>document.querySelector('input').addEventListener('change',()=>setTimeout(()=>document.querySelector('.se-section-text p').textContent='',0))")
  self.page.add_script_tag(path=str(ROOT/'chrome-extension/editor.js'));image=io.BytesIO();Image.new('RGB',(8,8),'red').save(image,'JPEG')
  result=self.page.evaluate("payload=>editorAction('fill',payload)",{'title':'제목','body':'첫 문단\n\n[[photo:1]]\n\n마지막 문단','photos':[{'name':'1.jpg','base64':base64.b64encode(image.getvalue()).decode()}],'transferId':'test-progress'})
  self.assertEqual(result['state'],'failed',result);self.assertIn('본문 전체',result['message']);self.assertEqual(result['count'],1)
  point=self.page.evaluate("()=>editorAction('progress',{transferId:'test-progress'})");self.assertEqual(point['state'],'finished');self.assertEqual(point['result']['state'],'failed');self.assertNotIn('첫 문단',json.dumps(point,ensure_ascii=False))
 def test_invalid_naver_photo_references_do_not_change_the_title(self):
  self.page.set_content(FIXTURE);self.page.add_script_tag(path=str(ROOT/'chrome-extension/editor.js'))
  result=self.page.evaluate("()=>editorAction('fill',{title:'입력되면 안 됨',body:'본문 [[photo:2]]',photos:[]})")
  self.assertEqual(result['state'],'failed');self.assertNotIn('입력되면',self.page.locator('.se-section-documentTitle').inner_text())
 def test_tistory_format_repair_preserves_text_photo_and_title(self):
  self.page.set_content(TISTORY);self.page.add_script_tag(path=str(ROOT/'chrome-extension/tistory.js'))
  self.page.evaluate("()=>{document.querySelector('#post-title-inp').value='유지할 제목';document.querySelector('#content').innerHTML='<p style=\"text-align:left\"><span style=\"font-family:Arial;font-size:11px\">보존할 본문</span></p><figure><img src=\"data:image/png;base64,aW1hZ2U=\"><figcaption>유지할 설명</figcaption></figure>';}")
  before=self.page.locator('#content').text_content();result=self.page.evaluate("()=>tistoryAction('format',{format:{align:'center'}})")
  self.assertEqual(result['state'],'ready',result);self.assertEqual(self.page.locator('#content').text_content(),before);self.assertEqual(self.page.locator('#content img').count(),1);self.assertEqual(self.page.locator('#post-title-inp').input_value(),'유지할 제목')
  self.assertEqual(self.page.locator('#content p').first.evaluate('el=>getComputedStyle(el).textAlign'),'center')
 def test_tistory_duplicate_insert_is_not_reported_as_completed(self):
  self.page.set_content(TISTORY);self.page.evaluate("()=>{const get=tinymce.get;tinymce.get=()=>{const editor=get();const insert=editor.insertContent;editor.insertContent=html=>{insert(html);insert(html)};return editor;};}");self.page.add_script_tag(path=str(ROOT/'chrome-extension/tistory.js'))
  result=self.page.evaluate("()=>tistoryAction('fill',{title:'제목',body:'한 번만 있어야 하는 문장',photos:[]})")
  self.assertEqual(result['state'],'failed',result)
