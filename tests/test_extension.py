import base64
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from PIL import Image
from playwright.sync_api import sync_playwright
from extension_bridge import ExtensionBridge,HandoffError
from naver_guard import NaverGuard

class BridgeProtocolTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.root=Path(self.temp.name)
        self.guard=NaverGuard(self.root/"guard.json")
        self.bridge=ExtensionBridge(self.root,self.guard)
        self.mid="a"*32
        (self.root/(self.mid+".jpg")).write_bytes(b"image")
        self.draft={"id":"b"*32,"title":"제목","blog":"본문","images":[self.mid]}
    def tearDown(self):
        self.temp.cleanup()
    def test_ticket_single_use_and_no_secrets(self):
        code=self.bridge.create(self.draft)["code"]
        payload=self.bridge.redeem(code)
        self.assertEqual(set(payload),{"title","body","photos","report_token","expected_photos","format"})
        with self.assertRaises(HandoffError):
            self.bridge.redeem(code)
        self.bridge.report(payload["report_token"],"ready",1)
        with self.assertRaises(ValueError):
            self.guard.reserve(self.draft["id"])
    def test_ticket_expiration(self):
        code=self.bridge.create(self.draft)["code"]
        with patch("extension_bridge.time.time",return_value=10**12):
            with self.assertRaises(HandoffError):
                self.bridge.redeem(code)
    def test_photo_mismatch_not_ready(self):
        payload=self.bridge.redeem(self.bridge.create(self.draft)["code"])
        with self.assertRaises(HandoffError):
            self.bridge.report(payload["report_token"],"ready",0)
        self.assertNotIn(self.draft["id"],self.guard.read()["completed"])
    def test_security_report_locks_guard(self):
        code=self.bridge.create(self.draft)["code"]
        self.bridge.block(code)
        self.assertTrue(self.guard.status()["blocked"])

    def test_partial_style_is_recorded_without_claiming_success(self):
        payload=self.bridge.redeem(self.bridge.create(self.draft)["code"])
        self.bridge.report(payload["report_token"],"partial",1)
        self.assertIn(self.draft["id"],self.guard.read()["completed"])
        with self.assertRaisesRegex(HandoffError,"같은 글 다시 넣기"):self.bridge.create(self.draft)
        with patch("naver_guard.time.time",return_value=10**12):
            new=self.bridge.create(self.draft,allow_repeat=True)
            payload=self.bridge.redeem(new["code"])
        self.assertEqual(payload["title"],self.draft["title"])
    def test_fresh_code_replaces_unused_code_for_same_draft(self):
        first=self.bridge.create(self.draft)["code"]
        for _ in range(8):second=self.bridge.create(self.draft)["code"]
        self.assertEqual(len(self.bridge.tickets),1)
        with self.assertRaises(HandoffError):self.bridge.redeem(first)
        self.assertIn("body",self.bridge.redeem(second))

    def test_valid_report_saves_diagnostic_without_payload_or_tokens(self):
        payload=self.bridge.redeem(self.bridge.create(self.draft)["code"])
        self.bridge.report(payload["report_token"],"partial",1,{"version":"1.3.0","stage":"서식 확인","formatting":{"alignment":False},"photos":["PRIVATE_PHOTO"],"token":payload["report_token"]})
        saved=(self.root/"naver-extension-diagnostics.json").read_text(encoding="utf-8")
        self.assertIn("서식 확인",saved)
        self.assertNotIn(payload["report_token"],saved)
        self.assertNotIn("PRIVATE_PHOTO",saved)

FIXTURE="""<!doctype html><style>.se-text-paragraph{min-height:30px}</style>
<div contenteditable="true">
<div class="se-section-documentTitle"><p class="se-text-paragraph"><span class="se-placeholder" contenteditable="false">제목</span></p></div>
<div class="se-section-text"><p class="se-text-paragraph"><span class="se-placeholder" contenteditable="false">내용</span></p></div>
</div><input type="file" accept="image/*" multiple>
<script>
document.addEventListener('input',()=>document.querySelectorAll('.se-placeholder').forEach(n=>n.remove()));
document.addEventListener('pointerdown',event=>{
 const section=event.target.closest('.se-section-text');if(section)window.lastEditSection=section;
});
document.querySelector('input').addEventListener('change',event=>{
 for(const file of event.target.files){
 const box=document.createElement('div');box.className='se-component se-image';
 const image=document.createElement('img');image.className='se-image-resource';image.src=URL.createObjectURL(file);box.append(image);
 image.alt=file.name;box.contentEditable='false';
 const next=document.createElement('div');next.className='se-section-text';
 next.innerHTML='<p class="se-text-paragraph"><br></p>';
 const anchor=window.lastEditSection||document.querySelector('.se-section-text');
 anchor.after(box,next);window.lastEditSection=next;}
});
</script>"""

class ExtensionEditorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.p=sync_playwright().start()
        cls.browser=cls.p.chromium.launch(headless=True)
        cls.script=Path(__file__).resolve().parents[1]/"chrome-extension"/"editor.js"
    @classmethod
    def tearDownClass(cls):
        cls.browser.close()
        cls.p.stop()
    def setUp(self):
        self.page=self.browser.new_page()
        self.page.set_content(FIXTURE)
        self.page.add_script_tag(path=str(self.script))
    def tearDown(self):
        self.page.close()
    def test_text_and_two_photos_entered(self):
        photos=[]
        for color in ("red","green"):
            image=io.BytesIO();Image.new("RGB",(8,8),color).save(image,"JPEG")
            photos.append({"name":color+".jpg","base64":base64.b64encode(image.getvalue()).decode()})
        result=self.page.evaluate("payload=>editorAction('fill',payload)",{"title":"확장 테스트","body":"첫 문단\n[[photo:1]]\n두 번째 문단\n[[photo:2]]","photos":photos})
        self.assertEqual(result["state"],"ready",result)
        self.assertEqual(result["count"],2)
    def test_text_photo_interleaving_preserves_positions(self):
        photos=[]
        for color in ("red","green"):
            image=io.BytesIO();Image.new("RGB",(8,8),color).save(image,"JPEG")
            photos.append({"name":color+".jpg","base64":base64.b64encode(image.getvalue()).decode()})
        result=self.page.evaluate("payload=>editorAction('fill',payload)",{
            "title":"사진 사이 이야기","body":"도입 문단\n\n[[photo:1]]\n\n첫 사진 감상\n\n[[photo:2]]\n\n마무리 문단","photos":photos})
        self.assertEqual(result["state"],"ready",result)
        order=self.page.evaluate("""()=>[...document.querySelectorAll('.se-section-text,.se-component.se-image')].map(el=>
            el.matches('.se-section-text')?el.innerText.trim():el.querySelector('img').alt).filter(Boolean)""")
        self.assertEqual(order,["도입 문단","red.jpg","첫 사진 감상","green.jpg","마무리 문단"])

    def test_pointer_activation_enables_editor(self):
        self.page.locator("[contenteditable=true]").evaluate("el=>el.removeAttribute('contenteditable')")
        self.page.evaluate("""()=>document.addEventListener('pointerdown',event=>{
            const section=event.target.closest('.se-section-documentTitle,.se-section-text');
            if(section)section.parentElement.contentEditable='true';
        })""")
        result=self.page.evaluate("()=>editorAction('fill',{title:'활성화 제목',body:'활성화 본문',photos:[]})")
        self.assertEqual(result["state"],"ready",result)

    def test_false_return_with_actual_input_is_accepted(self):
        self.page.evaluate("""()=>{
            const original=document.execCommand.bind(document);
            document.execCommand=(...args)=>{original(...args);return false;};
        }""")
        result=self.page.evaluate("()=>editorAction('fill',{title:'실제 반영 제목',body:'실제 반영 본문',photos:[]})")
        self.assertEqual(result["state"],"ready",result)

    def test_readonly_document_not_forced_editable(self):
        self.page.locator("[contenteditable=true]").evaluate("el=>el.removeAttribute('contenteditable')")
        result=self.page.evaluate("()=>editorAction('fill',{title:'제목',body:'본문',photos:[]})")
        self.assertEqual(result["state"],"failed")
        self.assertEqual(self.page.locator("[contenteditable=true]").count(),0)
        self.assertNotIn("본문",self.page.locator(".se-section-text").inner_text())


    def prepare_input_iframe(self,editable=True):
        self.page.set_content("""<!doctype html><style>.se-text-paragraph{min-height:30px}</style>
        <div class="se-section-documentTitle"><p class="se-text-paragraph"><span class="se-placeholder">제목</span></p></div>
        <div class="se-section-text"><p class="se-text-paragraph"><span class="se-placeholder">내용</span></p></div>
        <div contenteditable="true" hidden></div><iframe id="input-proxy"></iframe>""")
        frame=self.page.frames[1]
        frame.set_content('<body contenteditable="'+str(editable).lower()+'"></body>')
        self.page.evaluate("""()=>{
            const proxy=document.querySelector('iframe'),inner=proxy.contentDocument;
            document.addEventListener('pointerdown',event=>{
                const section=event.target.closest('.se-section-documentTitle,.se-section-text');
                if(!section)return;
                window.currentSection=section;
                inner.body.textContent='';
                inner.body.focus();
            });
            inner.body.addEventListener('input',()=>{
                if(window.currentSection)window.currentSection.querySelector('p').textContent=inner.body.textContent;
            });
            document.execCommand=()=>{throw Error('WRONG_PARENT_DOCUMENT');};
        }""")
        self.page.add_script_tag(path=str(self.script))

    def test_iframe_input_proxy_matches_user_diagnostic(self):
        self.prepare_input_iframe()
        self.assertEqual(self.page.locator('[contenteditable="true"]').count(),1)
        self.assertFalse(self.page.locator(".se-section-documentTitle").evaluate("el=>el.isContentEditable"))
        result=self.page.evaluate("()=>editorAction('fill',{title:'입력 프레임 제목',body:'프레임 본문',photos:[]})")
        self.assertEqual(result["state"],"ready",result)
        self.assertEqual(self.page.locator(".se-section-documentTitle").inner_text(),"입력 프레임 제목")
        self.assertEqual(self.page.locator(".se-section-text").inner_text(),"프레임 본문")

    def test_iframe_without_editable_target_stops(self):
        self.prepare_input_iframe(editable=False)
        # 읽기 전용 body.focus()만으로는 iframe 포커스가 가지 않으므로 프레임을 명시적으로 포커스한다.
        self.page.evaluate("""()=>document.addEventListener('click',event=>{
            if(event.target.closest('.se-section-documentTitle,.se-section-text'))document.querySelector('iframe').focus();
        })""")
        result=self.page.evaluate("()=>editorAction('fill',{title:'제목',body:'본문',photos:[]})")
        self.assertEqual(result["state"],"failed")
        self.assertEqual(result["diagnostics"]["activeTag"],"IFRAME")
        self.assertGreaterEqual(len(result["diagnostics"]["focusPath"]),2)
        self.assertNotIn("본문",self.page.locator(".se-section-text").inner_text())


    def test_proxy_that_flattens_paragraphs_is_not_reported_ready(self):
        self.prepare_input_iframe()
        result=self.page.evaluate("()=>editorAction('fill',{title:'제목',body:'첫 문단\\n\\n둘째 문단',photos:[]})")
        self.assertEqual(result["state"],"failed")
        self.assertIn("문단",result["message"])

    def test_input_proxy_enter_builds_real_paragraphs(self):
        self.prepare_input_iframe()
        self.page.evaluate("""()=>{
            const inner=document.querySelector('iframe').contentDocument,models=new WeakMap();
            const render=()=>{
                const section=window.currentSection;if(!section)return;
                section.replaceChildren(...models.get(section).map(text=>{
                    const p=document.createElement('p');p.className='se-text-paragraph';p.textContent=text;return p;
                }));
            };
            document.addEventListener('pointerdown',event=>{
                const section=event.target.closest('.se-section-documentTitle,.se-section-text');
                if(section)models.set(section,['']);
            });
            inner.body.addEventListener('input',event=>{
                event.stopImmediatePropagation();
                const model=models.get(window.currentSection);model[model.length-1]=inner.body.textContent;render();
            },true);
            inner.body.addEventListener('keydown',event=>{
                if(event.key!=='Enter')return;event.preventDefault();
                models.get(window.currentSection).push('');inner.body.textContent='';inner.body.focus();
                const range=inner.createRange();range.selectNodeContents(inner.body);range.collapse(false);
                inner.getSelection().removeAllRanges();inner.getSelection().addRange(range);render();
            });
        }""")
        result=self.page.evaluate("()=>editorAction('fill',{title:'제목',body:'첫 문단\\n\\n둘째 문단',photos:[]})")
        self.assertEqual(result["state"],"ready",result)
        self.assertEqual(self.page.locator(".se-section-text .se-text-paragraph").count(),3)
        self.assertIn("\n",self.page.locator(".se-section-text").inner_text())

    def test_photo_dialog_in_sibling_iframe_with_extension_accept(self):
        self.page.set_content('<button data-name="image">사진</button><iframe id="editor"></iframe>')
        frame=self.page.frames[1]
        frame.set_content(FIXTURE.replace('<input type="file" accept="image/*" multiple>','').split('<script>')[0])
        frame.add_script_tag(path=str(self.script))
        self.page.evaluate("""()=>{
            document.querySelector('button').onclick=()=>setTimeout(()=>{
                const uploader=document.createElement('iframe');document.body.append(uploader);
                const input=uploader.contentDocument.createElement('input');
                input.type='file';input.accept='.jpg,.jpeg,.png';input.multiple=true;
                uploader.contentDocument.body.append(input);
                const confirm=uploader.contentDocument.createElement('button');
                confirm.type='button';confirm.textContent='등록';confirm.disabled=true;
                uploader.contentDocument.body.append(confirm);
                input.onchange=()=>{confirm.disabled=false;};
                confirm.onclick=()=>{
                    const editor=document.querySelector('#editor').contentDocument;
                    for(const file of input.files){
                        const box=editor.createElement('div');box.className='se-component se-image';
                        const img=editor.createElement('img');img.className='se-image-resource';
                        img.src=URL.createObjectURL(file);box.append(img);
                        const next=editor.createElement('div');next.className='se-section-text';
                        next.contentEditable='true';next.innerHTML='<p class="se-text-paragraph"><br></p>';
                        editor.body.append(box,next);
                    }
                };
            },450);
        }""")
        image=io.BytesIO();Image.new("RGB",(8,8),"blue").save(image,"JPEG")
        photo={"name":"blue.jpg","base64":base64.b64encode(image.getvalue()).decode()}
        result=frame.evaluate("payload=>editorAction('fill',payload)",{"title":"제목","body":"본문","photos":[photo,photo]})
        self.assertEqual(result["state"],"ready",result)
        self.assertEqual(result["count"],2)

    def test_unavailable_font_is_reported_unverified(self):
        self.prepare_input_iframe()
        result=self.page.evaluate("payload=>editorAction('fill',payload)",{
            "title":"제목","body":"본문","photos":[],
            "format":{"align":"center","font":"마루 부리","font_key":"nanummaruburi","size":16}})
        self.assertEqual(result["state"],"partial",result)
        self.assertFalse(result["formatting"]["verified"])
        self.assertFalse(result["formatting"]["font"])
        self.assertIn("정렬·글꼴·크기",result["message"])

    def test_existing_content_is_preserved(self):
        self.page.locator(".se-section-documentTitle").evaluate("el=>el.textContent='기존 제목'")
        result=self.page.evaluate("()=>editorAction('fill',{title:'새 제목',body:'내용',photos:[]})")
        self.assertEqual(result["state"],"failed")
        self.assertEqual(self.page.locator(".se-section-documentTitle").inner_text(),"기존 제목")
    def test_security_prompt_stops_before_input(self):
        self.page.locator("body").evaluate("el=>el.insertAdjacentText('afterbegin','네이버 보호조치')")
        result=self.page.evaluate("()=>editorAction('probe',null)")
        self.assertTrue(result["blocked"])
        result=self.page.evaluate("()=>editorAction('fill',{title:'새 제목',body:'내용',photos:[]})")
        self.assertEqual(result["state"],"blocked")


    def test_mixed_span_font_size_is_not_reported_verified(self):
        self.page.locator("[contenteditable=true]").evaluate("el=>el.removeAttribute('contenteditable')")
        self.page.locator(".se-section-text").evaluate("el=>el.innerHTML='<p class=se-text-paragraph style=\"text-align:center;font-size:16px;font-family:MaruBuri\"><span>좋은 글</span><span style=\"font-size:15px;font-family:Arial\">다른 글</span></p>'")
        result=self.page.evaluate("()=>editorAction('format',{format:{align:'center',font:'마루 부리',font_key:'nanummaruburi',size:16}})")
        self.assertEqual(result["state"],"partial",result)
        self.assertFalse(result["formatting"]["font"])
        self.assertFalse(result["formatting"]["size"])
        self.assertTrue(result["formatting"]["alignment"])

    def test_alignment_option_menu_applies_and_preserves_text(self):
        self.prepare_input_iframe()
        self.page.locator(".se-section-text").evaluate("el=>el.innerHTML='<p class=se-text-paragraph>보존할 문장</p>'")
        self.page.evaluate("""()=>{
         const bar=document.createElement('div');bar.setAttribute('role','toolbar');
         bar.innerHTML='<button class="se-align-toolbar-button">정렬</button><div id="align-menu" hidden><button class="se-toolbar-option-align-center-button" data-name="align-drop-down-with-justify" data-value="center">가운데 정렬</button></div>';
         bar.querySelector('.se-align-toolbar-button').onclick=()=>{document.querySelector('#align-menu').hidden=false;};
         document.body.prepend(bar);
         bar.querySelector('.se-toolbar-option-align-center-button').onclick=()=>{
          document.querySelector('.se-section-text p').style.textAlign='center';document.querySelector('#align-menu').hidden=true;
         };
        }""")
        result=self.page.evaluate("()=>editorAction('format',{format:{align:'center',font:'마루 부리',font_key:'nanummaruburi',size:16}})")
        self.assertEqual(result["state"],"partial",result)
        self.assertTrue(result["formatting"]["alignment"],result)
        self.assertIn("보존할 문장",self.page.locator('.se-section-text').inner_text())
        self.assertTrue(any(item["alignmentOption"] for item in result["diagnostics"]["formatAttempts"]))

    def test_actual_diagnostic_dropdown_and_font_size_codes(self):
        self.prepare_input_iframe()
        self.page.locator(".se-section-text").evaluate("el=>el.innerHTML='<p class=se-text-paragraph>온천이 정말 좋았어요 ♨️</p>'")
        self.page.evaluate("""()=>{
         const bar=document.createElement('div');bar.setAttribute('role','toolbar');
         bar.innerHTML='<button class="se-font-family-toolbar-button" data-name="font-family">서체 변경</button><div id="font-list" hidden><button data-value="nanumbareunhipi">바른히피 서체 적용</button></div><button class="se-font-size-code-toolbar-button" data-name="font-size">15글자 크기 변경</button><div id="size-list" hidden><button data-value="fs13">13글자 크기</button></div><button class="se-property-toolbar-drop-down-button se-align-left-toolbar-button" data-name="align-drop-down-with-justify">정렬정렬 열기</button><div id="align-list" hidden><button class="se-toolbar-option-align-center-button" data-name="align-drop-down-with-justify" data-value="center">가운데 정렬 선택</button></div>';
         document.body.prepend(bar);
         bar.querySelector('[data-name="font-family"]').onclick=()=>{document.querySelector('#font-list').hidden=false;};
         bar.querySelector('[data-value="nanumbareunhipi"]').onclick=()=>{document.querySelector('.se-section-text').style.fontFamily='se-nanumbareunhipi';document.querySelector('#font-list').hidden=true;};
         bar.querySelector('[data-name="font-size"]').onclick=()=>{document.querySelector('#size-list').hidden=false;};
         bar.querySelector('[data-value="fs13"]').onclick=()=>{document.querySelector('.se-section-text').style.fontSize='13px';document.querySelector('#size-list').hidden=true;};
         bar.querySelector('[data-name="align-drop-down-with-justify"]').onclick=()=>{document.querySelector('#align-list').hidden=false;};
         bar.querySelector('[data-value="center"]').onclick=()=>{document.querySelector('.se-section-text p').style.textAlign='center';document.querySelector('#align-list').hidden=true;};
        }""")
        result=self.page.evaluate("()=>editorAction('format',{format:{align:'center',font:'나눔바른히피',font_key:'nanumbareunhipi',size:13}})")
        self.assertEqual(result["state"],"ready",result)
        self.assertTrue(result["formatting"]["verified"],result)
        self.assertIn("온천이 정말 좋았어요 ♨️",self.page.locator('.se-section-text').inner_text())
        self.assertTrue(result["diagnostics"]["formatAttempts"][0]["alignmentMenu"])
        self.assertTrue(result["diagnostics"]["formatAttempts"][0]["sizeOption"])

    def test_proxy_font_needs_editor_model_keyboard_selection(self):
        self.prepare_input_iframe()
        self.page.locator(".se-section-text").evaluate("el=>el.innerHTML='<p class=se-text-paragraph style=\"text-align:center;font-size:15px;font-family:Arial\">첫 줄</p><p class=se-text-paragraph style=\"text-align:center;font-size:15px;font-family:Arial\">둘째 줄 🤍</p>'")
        self.page.evaluate("""()=>{
         const inner=document.querySelector('iframe').contentDocument;
         inner.body.addEventListener('keydown',event=>{
          if(event.ctrlKey&&event.key==='a'){event.preventDefault();window.modelSelected=true;}
         });
         const bar=document.createElement('div');
         bar.innerHTML='<button class="se-font-family-toolbar-button" data-name="font-family">서체 변경</button><div id="font-list" hidden><button data-name="font-family" data-value="nanumbareunhipi"><span>바른히피</span><span>바른히피</span></button></div>';
         document.body.prepend(bar);
         bar.querySelector('.se-font-family-toolbar-button').onclick=()=>{document.querySelector('#font-list').hidden=false;};
         bar.querySelector('[data-value]').onclick=()=>{
          if(window.modelSelected)document.querySelectorAll('.se-section-text p').forEach(p=>p.style.fontFamily='se-nanumbareunhipi');
          document.querySelector('#font-list').hidden=true;
         };
        }""")
        result=self.page.evaluate("()=>editorAction('format',{format:{align:'center',font:'나눔바른히피',font_key:'nanumbareunhipi',size:15}})")
        self.assertEqual(result["state"],"ready",result)
        self.assertTrue(result["formatting"]["font"])
        self.assertIn("둘째 줄 🤍",self.page.locator('.se-section-text').inner_text())
