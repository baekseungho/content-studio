"""글쓰기 품질 점검과 사용자 선택 안내 문구. 외부 API를 호출하지 않는다."""
import re
from campaigns import mission_checks
DISCLOSURES={"none":"","gifted":"제품을 제공받아 작성한 글입니다.","paid":"광고비를 지급받아 작성한 글입니다.","experience":"식사 또는 이용권을 제공받아 작성한 글입니다."}

DISCLOSURES_EN={"none":"","gifted":"This product was provided for this post.","paid":"Paid partnership.","experience":"A meal or service voucher was provided for this post."}

def disclose(value,kind,language="ko"):
    for sentence in (*DISCLOSURES.values(),*DISCLOSURES_EN.values()):
        if sentence:
            value=re.sub(r"(?m)^"+re.escape(sentence)+r"\s*\n?","",value)
    sentence=(DISCLOSURES_EN if language=="en" else DISCLOSURES).get(kind,"")
    return (sentence+"\n\n"+value.lstrip()).strip() if sentence else value.strip()

def review(draft):
    checks=[]
    def add(level,message):
        checks.append({"level":level,"message":message})
    if draft.get("review_channel")=="instagram":
        caption=draft.get("instagram","").strip()
        if not caption:add("error","인스타그램 글이 비어 있어요.")
        if len(caption)>2200:add("error","인스타그램 캡션이 2,200자를 넘어요.")
        if not draft.get("images"):add("warning","인스타그램 발행에는 사진이 필요해요.")
        if draft.get("language")=="en" and re.search(r"[가-힣]",draft.get("facts","")) and not caption_facts(draft):add("error","인스타그램 영어 필수 메모가 바뀌었어요. 이 플랫폼 글을 다시 만들면 반영할 수 있어요.")
        if not checks:add("info","인스타그램 글과 사진이 준비됐어요. 내용을 확인한 뒤 발행해 주세요.")
        return checks
    if draft.get("review_channel")=="threads":
        value=draft.get("threads","").strip()
        if not value:add("error","Threads 글이 비어 있어요.")
        if len(value)>500:add("error","Threads 글이 500자를 넘어요.")
        if not checks:add("info","Threads 본문이 준비됐어요. 사진과 마지막 발행은 Threads에서 확인해 주세요.")
        return checks
    if draft.get("review_channel") not in ("threads","instagram"):
        for check in mission_checks(draft):
            if not check["passed"]:add("error","체험단 미션 · "+check["label"]+" 확인 필요 ("+check["detail"]+")")
    title=draft.get("title","").strip()
    blog=draft.get("blog","").strip()
    insta=draft.get("instagram","").strip()
    if not title:add("error","블로그 제목이 비어 있어요.")
    if not blog:add("error","블로그 본문이 비어 있어요.")
    if not insta:add("warning","인스타그램 캡션이 비어 있어요.")
    if len(insta)>2200:add("error","인스타그램 캡션이 2,200자를 넘어요.")
    threads=draft.get("threads","")
    if len(threads)>500:add("error","Threads 글이 500자를 넘어요. 내용을 줄여 주세요.")
    if draft.get("language")=="en" and draft.get("facts") and re.search(r"[가-힣]",draft["facts"]) and (not draft.get("facts_translation") or draft.get("facts_translation_source")!=draft["facts"]):
        add("warning","영어 글의 필수 메모가 바뀌었어요. 글을 다시 만들면 영어로 반영할 수 있어요.")
    images=draft.get("images",[])
    if not images:add("warning","선택한 사진이 없어요. 인스타그램 발행에는 사진이 필요해요.")
    else:add("info",f"선택한 사진 {len(images)}장. 네이버 입력 뒤에도 실제 사진 수를 확인해 주세요.")
    if re.search(r"확인[이 ]*필요|확인해\s*주세요|\[.*?(?:입력|확인).*?\]|정보가\s*없",blog):
        add("warning","본문에 확인 필요 문구나 미완성 항목이 있어요.")
    facts=draft.get("prompt","")+" "+draft.get("facts","")+" "+(draft.get("campaign_brief","") if draft.get("campaign_enabled") else "")
    prices=re.findall(r"\d[\d,]*\s*원",blog)
    if any(p.replace(" ","") not in facts.replace(" ","") for p in prices):
        add("warning","직접 입력한 정보에 없는 가격이 있어요. 최신 메뉴판·공식 자료와 확인해 주세요.")
    if re.search(r"https?://|cite",blog):
        add("warning","본문에 링크나 검색 인용 문법이 남아 있어요.")
    if len(re.findall(r"#[^\s#]+",insta))>10:
        add("warning","해시태그가 10개를 넘어요. 핵심 태그만 남겨 보세요.")
    if not draft.get("facts","").strip():
        add("warning","직접 경험한 사실이 비어 있어요. 맛·가격·방문 경험이 실제와 같은지 확인해 주세요.")
    if draft.get("disclosure","none")!="none":
        add("info","선택한 광고·제품 제공 안내를 글 첫머리에 반영했어요.")
    add("info","자동 점검은 사실 검증이 아니에요. 장소·가격·운영시간·사진 속 개인정보를 마지막으로 확인해 주세요.")
    return checks


def required_instagram_story(caption,facts):
    """Keep explicitly required notes intact, before the trailing hashtag block."""
    if not caption.strip() or not facts.strip():return caption
    compact=lambda value:re.sub(r"\s+","",value)
    present=compact(caption)
    missing=[]
    for line in facts.replace("\r\n","\n").replace("\r","\n").split("\n"):
        line=line.strip()
        if line and compact(line.rstrip(".!?。…")) not in present:
            missing.append(line);present+=compact(line)
    if not missing:return caption
    # Only move a final hashtag-only block; leave in-sentence hashtags untouched.
    match=re.search(r"(?:^|\n)([ \t]*#[^\s#]+(?:\s+#[^\s#]+)*[ \t]*)$",caption)
    end=match.start() if match else len(caption)
    parts=[caption[:end].rstrip(),"\n".join(missing)]
    if match:parts.append(match.group(1).strip())
    return "\n\n".join(part for part in parts if part)


def caption_facts(draft):
    facts=draft.get("facts","")
    if draft.get("language")!="en" or not re.search(r"[가-힣]",facts):return facts
    if draft.get("facts_translation_source")==facts and not re.search(r"[가-힣]",draft.get("facts_translation","")):return draft.get("facts_translation","")
    return ""
