"""글쓰기 품질 점검과 사용자 선택 안내 문구. 외부 API를 호출하지 않는다."""
import re
DISCLOSURES={"none":"","gifted":"제품을 제공받아 작성한 글입니다.","paid":"광고비를 지급받아 작성한 글입니다."}

def disclose(value,kind):
    for sentence in DISCLOSURES.values():
        if sentence:
            value=re.sub(r"(?m)^"+re.escape(sentence)+r"\s*\n?","",value)
    sentence=DISCLOSURES.get(kind,"")
    return (sentence+"\n\n"+value.lstrip()).strip() if sentence else value.strip()

def review(draft):
    checks=[]
    def add(level,message):
        checks.append({"level":level,"message":message})
    title=draft.get("title","").strip()
    blog=draft.get("blog","").strip()
    insta=draft.get("instagram","").strip()
    if not title:add("error","블로그 제목이 비어 있어요.")
    if not blog:add("error","블로그 본문이 비어 있어요.")
    if not insta:add("warning","인스타그램 캡션이 비어 있어요.")
    if len(insta)>2200:add("error","인스타그램 캡션이 2,200자를 넘어요.")
    images=draft.get("images",[])
    if not images:add("warning","선택한 사진이 없어요. 인스타그램 발행에는 사진이 필요해요.")
    else:add("info",f"선택한 사진 {len(images)}장. 네이버 입력 뒤에도 실제 사진 수를 확인해 주세요.")
    if re.search(r"확인[이 ]*필요|확인해\s*주세요|\[.*?(?:입력|확인).*?\]|정보가\s*없",blog):
        add("warning","본문에 확인 필요 문구나 미완성 항목이 있어요.")
    facts=draft.get("prompt","")+" "+draft.get("facts","")
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
