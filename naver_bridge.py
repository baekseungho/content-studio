"""네이버 SmartEditor 입력 도우미. 직접 로그인한 빈 편집기만 입력한다."""
import json
import os
from pathlib import Path
import re
import sys
import time
from urllib.parse import quote, urlparse
from playwright.sync_api import sync_playwright, TimeoutError as BrowserTimeout
from app import DATA, MEDIA, get_draft
from content_rules import clean_blog
from naver_guard import NaverGuard

TITLE_SELECTOR = ".se-section-documentTitle"
BODY_SELECTOR = ".se-section-text"
class BridgeError(Exception):
    pass

def check_protection(context):
    for page in context.pages:
        if page.is_closed():
            continue
        for frame in page.frames:
            try:
                text=frame.locator("body").inner_text(timeout=1500)
                captcha=frame.locator('#captchaimg, input#captcha, img[alt*="자동입력"]').count()
            except Exception:
                continue
            if captcha or any(word in text for word in ("보호조치","보호 조치","비정상적인 활동","자동입력 방지문자","2단계 인증","이용이 제한")):
                reason="네이버 보호조치·추가 인증 화면이 감지되어 자동 입력을 중단했어요. 공식 네이버 화면에서 직접 계정을 확인해 주세요."
                NaverGuard(DATA/"naver-guard.json").block(reason)
                raise BridgeError(reason)

def loaded_photo_count(frame):
    resources=frame.locator("img.se-image-resource")
    if not resources.count():
        resources=frame.locator(".se-component.se-image img, .se-component.se-imageStrip img, .se-component.se-imageGroup img")
    return resources.evaluate_all("images=>images.filter(img=>img.complete && img.naturalWidth>0).length")

def visible_first(scope, selector):
    locators = scope.locator(selector)
    for i in range(locators.count()):
        item = locators.nth(i)
        if item.is_visible():
            return item
    return None

def find_editor(context):
    # SmartEditor는 조상 노드에서 편집 속성을 상속하기도 한다.
    # 자식에 contenteditable=true가 있어야 한다고 가정하지 않는다.
    for page in reversed(context.pages):
        if page.is_closed():
            continue
        for frame in page.frames:
            try:
                title = visible_first(frame, TITLE_SELECTOR)
                body = visible_first(frame, BODY_SELECTOR)
                if title is not None and body is not None:
                    return page, frame, title, body
            except Exception:
                continue
    return None

def editor_text(section):
    return section.evaluate("""el => {
        const clone=el.cloneNode(true);
        clone.querySelectorAll('.se-placeholder,.se-help-placeholder,.se-guide').forEach(n=>n.remove());
        return (clone.textContent||'').replace(/\\u200b/g,'').trim();
    }""")

def click_paragraph(section):
    target = visible_first(section, ".se-text-paragraph")
    if target is None:
        target = visible_first(section, ".se-text")
    target = target if target is not None else section
    target.click(timeout=10000)
    # placeholder 위 클릭으로 커서가 편집 영역 바깥에 생기는 경우를 방지한다.
    # 문서는 바꾸지 않고 선택 범위만 문단 끝에 둔 뒤 실제 키보드 입력을 보낸다.
    target.evaluate("""el => {
        let editable=el;
        while(editable && !editable.hasAttribute('contenteditable'))editable=editable.parentElement;
        if(editable && editable.getAttribute('contenteditable')!=='false')editable.focus();
        const range=document.createRange();
        range.selectNodeContents(el);range.collapse(false);
        const selection=window.getSelection();
        selection.removeAllRanges();selection.addRange(range);
    }""")

def insert_lines(page, value):
    lines = value.split("\n")
    for i, line in enumerate(lines):
        if i:
            page.keyboard.press("Enter")
        if line:
            page.keyboard.insert_text(line)

def upload_photos(page,frame,paths):
    if not paths:
        return
    before=loaded_photo_count(frame)
    # 사진 선택 상태에서 숨겨진 input을 재사용하면 기존 사진을 교체할 수 있다.
    # 선택 사진 전체를 새 업로드 동작 한 번으로 넣는다.
    button=frame.locator('button[data-name="image"], button.se-image-toolbar-button').first
    if button.count():
        try:
            with page.expect_file_chooser(timeout=4000) as chooser:
                button.click(timeout=10000)
        except BrowserTimeout:
            target=None
            for scope in (frame,page):
                for label in ("내 컴퓨터","컴퓨터에서 사진 선택","내 컴퓨터에서"):
                    candidate=scope.get_by_text(label,exact=True)
                    if candidate.count() and candidate.first.is_visible():
                        target=candidate.first
                        break
                if target is not None:
                    break
            if target is None:
                raise BridgeError("사진 선택 메뉴를 찾지 못했어요. 같은 작업을 반복하지 말고 열린 편집기를 확인해 주세요.")
            with page.expect_file_chooser(timeout=10000) as chooser:
                target.click()
        if len(paths)>1 and not chooser.value.is_multiple():
            raise BridgeError("현재 사진 선택기가 여러 장을 지원하지 않아요. 열린 편집기에서 사진을 직접 추가해 주세요.")
        chooser.value.set_files([str(path) for path in paths])
    else:
        file_input=frame.locator('input[type="file"][accept*="image"]').first
        if not file_input.count():
            raise BridgeError("사진 업로드 버튼을 찾지 못했어요. 열린 편집기에서 직접 사진을 추가해 주세요.")
        if len(paths)>1 and not file_input.get_attribute("multiple")=="" and not file_input.evaluate("el=>el.multiple"):
            raise BridgeError("사진 선택기가 한 장만 지원해요. 여러 장을 직접 추가해 주세요.")
        file_input.set_input_files([str(path) for path in paths])
    deadline=time.monotonic()+45
    expected=before+len(paths)
    while time.monotonic()<deadline:
        check_protection(page.context)
        if loaded_photo_count(frame)==expected:
            return
        page.wait_for_timeout(300)
    raise BridgeError(f"사진 {len(paths)}장을 요청했지만 새로 로딩된 사진은 {max(0,loaded_photo_count(frame)-before)}장이에요. 완료로 처리하지 않았어요. 재시도하지 말고 열린 편집기에서 확인해 주세요.")


def fill_editor(page, frame, title, body, draft, report):
    check_protection(page.context)
    if editor_text(title) or editor_text(body) or frame.locator(".se-component.se-image").count():
        raise BridgeError("이미 내용이 있는 편집기는 덮어쓰지 않아요. 빈 새 글을 열고 다시 실행해 주세요.")
    # 도움말 패널만 닫는다. 임시글/발행 확인 같은 사용자 선택 팝업은 건드리지 않는다.
    help_close = visible_first(frame, ".se-help-panel-close-button")
    if help_close is not None:
        help_close.click()
    report("running", "네이버 제목을 입력하고 있어요.")
    try:
        click_paragraph(title)
        page.keyboard.insert_text(draft["title"])
        if editor_text(title).strip() != draft["title"].strip():
            raise BridgeError("제목 입력이 반영되지 않았어요. 편집기의 팝업이나 읽기 전용 상태를 확인해 주세요.")
        click_paragraph(body)
    except BrowserTimeout:
        raise BridgeError("편집기를 누를 수 없어요. 열린 네이버 창의 도움말·임시글 팝업을 닫고 다시 시도해 주세요.")
    report("running", "네이버 본문과 사진을 입력하고 있어요.")
    expected_text=[]
    for line in clean_blog(draft["blog"]).splitlines():
        check_protection(page.context)
        if re.fullmatch(r"\s*\[\[photo:(\d+)\]\]\s*",line):
            continue
        value=line.removeprefix("## ")
        insert_lines(page,value)
        page.keyboard.press("Enter")
        if value.strip():
            expected_text.append(value.strip())
    paths=[MEDIA/(mid+".jpg") for mid in draft["images"]]
    for path in paths:
        if not path.is_file():
            raise BridgeError("선택한 사진 파일이 없어요. 사진 목록을 확인해 주세요.")
    if paths:
        report("running",f"선택한 사진 {len(paths)}장을 본문 아래에 한 번에 넣고 있어요.")
        upload_photos(page,frame,paths)
    actual_body = " ".join(editor_text(s) for s in frame.locator(BODY_SELECTOR).all())
    normalize = lambda value: re.sub(r"\s+", "", value)
    if expected_text and any(normalize(value) not in normalize(actual_body) for value in expected_text):
        raise BridgeError("본문 일부가 입력되지 않았어요. 열린 편집기에서 내용을 확인해 주세요.")
    if loaded_photo_count(frame) != len(draft["images"]):
        raise BridgeError("일부 사진 입력을 확인하지 못했어요. 사진 배치를 확인해 주세요.")

def diagnostics(context):
    frames=[]
    for page in context.pages:
        for frame in page.frames:
            try:
                frames.append({"host":urlparse(frame.url).hostname,
                    "title_sections":frame.locator(TITLE_SELECTOR).count(),
                    "body_sections":frame.locator(BODY_SELECTOR).count(),
                    "editable_nodes":frame.locator('[contenteditable="true"]').count()})
            except Exception:
                pass
    # 글 내용, 쿠키, 전체 URL, 계정 정보는 진단 파일에 기록하지 않는다.
    (DATA/"naver-diagnostics.json").write_text(json.dumps({"frames":frames}),encoding="utf-8")

def main(did, marker):
    draft = get_draft(did)
    blog_id = os.environ.get("NAVER_BLOG_ID", "")
    if not re.fullmatch(r"[a-zA-Z0-9_-]+", blog_id):
        raise BridgeError("NAVER_BLOG_ID 설정을 확인해 주세요.")
    def report(state, message):
        temp = marker.with_suffix(".tmp")
        temp.write_text(json.dumps({"state":state,"message":message},ensure_ascii=False),encoding="utf-8")
        temp.replace(marker)
    report("running", "네이버 브라우저를 여는 중이에요.")
    with sync_playwright() as p:
        context = p.chromium.launch_persistent_context(
            str(DATA/"naver-browser"),headless=False,viewport={"width":1280,"height":900})
        try:
            page = context.pages[0] if context.pages else context.new_page()
            page.goto("https://blog.naver.com/"+quote(blog_id)+"?Redirect=Write&",
                      wait_until="domcontentloaded",timeout=30000)
            report("running", "네이버 로그인을 기다리고 있어요. 열린 창에서 로그인과 추가 인증을 마쳐 주세요.")
            deadline = time.monotonic()+180
            found = None
            while time.monotonic()<deadline:
                if not context.pages:
                    raise BridgeError("네이버 창이 닫혀 입력을 중단했어요.")
                check_protection(context)
                found = find_editor(context)
                if found:
                    break
                context.pages[0].wait_for_timeout(500)
            if not found:
                diagnostics(context)
                raise BridgeError("3분 안에 네이버 편집기를 찾지 못했어요. 로그인 후 빈 글쓰기 화면을 열어 주세요.")
            fill_editor(*found,draft,report)
            report("editor_ready",f"글과 사진 {len(draft['images'])}/{len(draft['images'])}장의 로딩을 확인했어요. 사진은 본문 아래에 모았어요. 열린 네이버 창에서 배치·내용을 확인한 후 발행해 주세요.")
            while context.pages:
                try:
                    context.pages[0].wait_for_timeout(1000)
                except Exception:
                    break
        except Exception as error:
            diagnostics(context)
            if isinstance(error,BridgeError):
                message=str(error)
            elif isinstance(error,BrowserTimeout):
                message="네이버 화면 응답 시간이 초과됐어요. 로그인·팝업·네트워크 상태를 확인해 주세요."
            else:
                message="네이버 입력 중 오류가 발생했어요. 열린 편집기를 확인해 주세요."
            report("failed",message)
            # 실패한 부분을 사용자가 확인할 수 있도록 창을 유지한다.
            while context.pages:
                try:
                    context.pages[0].wait_for_timeout(1000)
                except Exception:
                    break
        finally:
            context.close()

if __name__=="__main__":
    marker=Path(sys.argv[2])
    try:
        main(sys.argv[1],marker)
    except Exception:
        temp=marker.with_suffix(".tmp")
        temp.write_text(json.dumps({"state":"failed","message":"네이버 도우미를 시작하지 못했어요. 다른 도우미 창을 닫고 브라우저 설치를 확인해 주세요."}),encoding="utf-8")
        temp.replace(marker)
        sys.exit(1)
