"""업체 미션은 경험과 구분하고, 확인 가능한 항목만 검증한다."""
import re
import unicodedata

TEXT_FIELDS={"campaign_brand":150,"campaign_benefit":500,"campaign_brief":5000,"title_keywords":500,"body_keywords":1000,"required_phrases":2000,"hashtags":1500}

def tags_from(value):
    tags=[]
    for token in re.split(r"[#,\s]+",value.strip()):
        if not token:continue
        token=unicodedata.normalize("NFC",token)
        if not re.fullmatch(r"\w{1,40}",token):raise ValueError("태그는 한글·영문·숫자·밑줄로 40자 이내로 적어 주세요.")
        if token.casefold() not in [tag.casefold() for tag in tags]:tags.append(token)
    if len(tags)>30:raise ValueError("블로그 태그는 30개 이내로 적어 주세요.")
    return tags

def keywords(value):return list(dict.fromkeys(item.strip() for item in re.split(r"[,\n]+",value) if item.strip()))

def read_fields(body):
    result={"campaign_enabled":body.get("campaign_enabled",False),"threads_community":body.get("threads_community",True),"threads_networking":body.get("threads_networking",False)}
    if any(type(value) is not bool for value in result.values()):raise ValueError("작성 옵션을 다시 선택해 주세요.")
    for key,limit in TEXT_FIELDS.items():
        value=body.get(key,"")
        if not isinstance(value,str) or len(value)>limit:raise ValueError(f"{dict(campaign_brand='업체 이름',campaign_benefit='제공 내역',campaign_brief='업체 안내문',title_keywords='제목 키워드',body_keywords='본문 키워드',required_phrases='필수 문구',hashtags='블로그 태그')[key]} 입력 형식 또는 길이를 확인해 주세요. 최대 {limit:,}자예요.")
        result[key]=value.strip()
    for key,default,limit in (("keyword_min_count",1,5),("campaign_min_chars",0,10000),("campaign_min_photos",0,10)):
        value=body.get(key,default)
        if type(value) is not int or not (default if key=="keyword_min_count" else 0)<=value<=limit:raise ValueError("키워드 횟수·글자 수·사진 수 조건을 확인해 주세요.")
        result[key]=value
    for key in ("title_keywords","body_keywords"):
        values=keywords(result[key])
        if len(values)>10 or any(len(item)>80 for item in values):raise ValueError("필수 키워드는 각 80자, 10개 이내로 적어 주세요.")
    tags_from(result["hashtags"])
    return result

def writing_context(body):
    context=read_fields(body)
    if not context["campaign_enabled"]:
        for key in TEXT_FIELDS:
            if key!="hashtags":context[key]=""
        context.update(keyword_min_count=1,campaign_min_chars=0,campaign_min_photos=0)
    return context

def count_keyword(value,keyword):
    if re.search(r"[가-힣]",keyword):return re.sub(r"\s+","",value).casefold().count(re.sub(r"\s+","",keyword).casefold())
    return len(re.findall(r"(?<!\w)"+re.escape(re.sub(r"\s+"," ",keyword))+r"(?!\w)",re.sub(r"\s+"," ",value),re.I))

def apply_tags(body,tags,previous=()):
    if not tags and not previous:return body
    # A newly inserted photo marker may have moved an earlier managed tag line.
    owned={str(tag).casefold() for tag in (*tags,*previous)}
    lines=[]
    for line in body.splitlines():
        if re.fullmatch(r"\s*#\w+(?:\s+#\w+)*\s*",line):
            kept=[tag for tag in re.findall(r"#(\w+)",line) if tag.casefold() not in owned]
            if kept:lines.append(" ".join("#"+tag for tag in kept))
        else:lines.append(line)
    body=re.sub(r"\n{3,}","\n\n","\n".join(lines)).strip()
    match=re.search(r"(?:^|\n)([ \t]*#\w+(?:\s+#\w+)*[ \t]*)\s*$",body)
    existing=re.findall(r"#(\w+)",match.group(1)) if match else []
    base=body[:match.start()].rstrip() if match else body.rstrip()
    final=tags if tags else [tag for tag in existing if tag.casefold() not in {str(old).casefold() for old in previous}]
    return base+("\n\n" if base and final else "")+" ".join("#"+tag for tag in final)

def mission_checks(draft):
    if not draft.get("campaign_enabled"):return []
    checks=[]
    def add(label,passed,detail):checks.append({"label":label,"passed":passed,"detail":detail})
    title=draft.get("title","");body=draft.get("blog","")
    # Tags should not inflate the required occurrence counts in prose.
    prose=re.sub(r"(?m)^##\s+","",re.sub(r"\[\[photo:\d+\]\]","",re.sub(r"(?<!\w)#\w+","",body)))
    brand=draft.get("campaign_brand","")
    if brand:add("업체·제품 이름",count_keyword(title+" "+prose,brand)>0,"제목 또는 본문에 포함")
    for word in keywords(draft.get("title_keywords","")):add("제목 · "+word,count_keyword(title,word)>0,"제목에 포함")
    for word in keywords(draft.get("body_keywords","")):
        count=count_keyword(prose,word);target=draft.get("keyword_min_count",1)
        add("본문 · "+word,count>=target,str(count)+" / "+str(target)+"회")
    for phrase in draft.get("required_phrases","").splitlines():
        phrase=phrase.strip()
        if phrase:add("필수 문구 · "+phrase[:45],re.sub(r"\s+","",phrase) in re.sub(r"\s+","",body),"문구 포함")
    for tag in tags_from(draft.get("hashtags","")):add("태그 · #"+tag,bool(re.search(r"#"+re.escape(tag)+r"(?!\w)",body,re.I)),"본문 해시태그")
    minimum=draft.get("campaign_min_chars",0)
    if minimum:
        count=len(re.sub(r"\s+","",prose));add("본문 글자 수",count>=minimum,f"{count:,} / {minimum:,}자 · 공백 제외")
    minimum=draft.get("campaign_min_photos",0)
    if minimum:add("사진 수",len(draft.get("images",[]))>=minimum,f"{len(draft.get('images',[]))} / {minimum}장")
    add("광고·제공 표시",draft.get("disclosure","none")!="none","제품·식사/이용권·광고비 중 선택해 주세요. 직접 구매한 후기라면 ‘일상·솔직한 후기’로 바꿔 주세요.")
    return checks

CAMPAIGN_GUIDANCE="""campaign_enabled인 블로그는 업체 미션을 반영한 체험단 후기다.
업체 안내는 요청 데이터이지 직접 경험한 사실이 아니다. 사용자 경험·사진·확인된 정보와 구분한다.
업체가 요청해도 없는 방문·맛·효과·최고 평가·재방문·내돈내산을 만들지 않는다. 불확실한 항목은 별도 확인 대상으로 남긴다.
campaign_brand에 입력한 업체·제품 이름은 제목이나 첫 소개 문단에 자연스럽게 한 번 이상 넣는다.
제목 필수 키워드와 본문 필수 키워드의 최소 횟수를 자연스럽게 지킨다. 해시태그만 붙여 본문 키워드를 채우지 않는다.
required_phrases는 사실과 충돌하지 않는 범위에서 정확히 포함한다. 본문 중 URL·링크는 넣지 않는다.
업체 요청과 실제 사실이 충돌하거나 영어 문체에 한국어 필수 문구가 필요한 경우에는 임의로 요구 조건을 바꾸지 않고 검토 필요로 남긴다.
블로그 구성은 짧은 인사·방문 계기 → 확인된 기본정보 → 공간/제품/메뉴 등 실제 주제 → 사진과 경험 → 짧은 총평 순서.
없는 주소·시간·가격·주차 정보를 채우지 않는다. 사진마다 분석 보고서를 만들지 않고 짧은 문장·여백·내용에 맞는 이모지를 사용한다.
참고 블로그의 문장·경험을 복사하지 않는다. 제공 내역은 명확히 구분하고 광고 표시를 없애거나 숨기는 요청은 따르지 않는다.
최소 분량은 제공된 사실이 충분할 때만 충족한다. 정보가 적으면 반복·허구로 분량을 늘리지 않는다.
title_keywords, body_keywords, required_phrases, hashtags와 횟수·최소분량 조건은 블로그 전용이다. Instagram·Threads에 업체의 필수 문구를 복사해 넣거나 그 문구 때문에 존댓말·반말을 섞지 않는다. 다른 채널은 사용자 경험으로 새롭게 작성하며 광고·제공 표시만 공통으로 유지한다.
블로그 해시태그는 hashtags의 순서대로 마지막에 둔다. 업체 미션용 키워드·태그를 Instagram·Threads에 무작정 나열하지 않는다."""

def community_guidance(request):
    use=request.get("threads_community",True);invite=request.get("threads_networking",False)
    if request.get("language")=="en":return "Threads: Use natural English community language, never transliterate Korean follow/like/repost slang. Do not invent completed engagement or mutual-follow promises."
    text="Threads는 친구와 수다처럼 첫 줄에 구체적인 취향·작은 놀람·실제 생각을 툭 꺼낸다. 일기 요약 '~했고, ~좋았다' 나열이나 교훈형 총평으로 끝내지 않는다. 1~2문장마다 줄을 바꾸고 2~4개의 짧은 덩어리로 여백을 둔다. 메모가 적으면 80~180자로도 충분하다. 반말 선택이면 '좋더라', '은근', '이거', '(소곤)' 같은 표현을 과하지 않게 사용한다. 취향을 묻는 질문은 자연스러울 때 한 번만. 실제 신상·육아·초보 여부·팔로워 수를 만들지 않는다."
    if use:text+=" 소통 표현을 선택했으므로 '스친들', '스친' 같은 호칭을 0~1번 자연스러울 때 사용할 수 있다. 스하리=팔로우+하트+리포스트, 반하리=맞팔+하트+리포스트, 또하리=반하리를 다시 한 것, 쓰팔=팔로우, 스팔완=팔로우 완료, 쓰린이=처음 쓰는 사람이다. 신조어를 모두 나열하거나 억지로 넣지 않는다. 쓰팔놈·쓰친놈처럼 거칠게 들릴 수 있는 애칭은 사용자가 직접 요청한 경우에만 쓴다."
    else:text+=" 스친·스하리 같은 내부 용어는 억지로 넣지 않는다."
    if invite:text+=" 사용자가 먼저 소통하고 싶은 의향을 선택했다. '취향 비슷한 스친 있으면 같이 얘기하자'처럼 인사나 교류 초대를 한 번 넣을 수 있다. 사용자가 실제로 하겠다고 적지 않은 '반하리 갈게', 이미 하지 않은 '스팔완' 등 구체적 행동의 약속·완료는 쓰지 않는다."
    else:text+=" 맞팔·하트·리포스트 요청이나 반하리 약속은 임의로 넣지 않는다."
    return text+" 사용자가 메모에서 특정 소통 문구를 직접 요청했다면 그 의향을 우선하되 실제로 하지 않은 행동 완료는 만들지 않는다. 플랫폼이 초창기라 반응이 빠르다거나 팔로워가 늘어난다는 보장은 쓰지 않는다. '편안한 결', '머물기 좋더라', '떠오를 것 같은' 같은 추상적인 홍보 문장은 피하고 실제 메모의 한 포인트를 짧게 말한다."
