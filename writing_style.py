"""후기 문체 지침과 생성 결과의 모바일 줄 나누기. 원문 정보는 바꾸지 않는다."""
import re
import textwrap

BLOG_GUIDANCE="""블로그는 사진 분석 보고서가 아니라 사용자가 직접 남기는 편안한 여행·일상 후기다.
'첫 번째 사진은', '두 번째 사진에서는', '사진 3번', '이 사진은', '마지막 사진은'처럼 업로드 순서를 설명하는 문장은 쓰지 않는다.
사진 순서는 위치 표시로만 관리하고 글에서는 온천·객실·뷰·욕실처럼 실제 이야기의 주제로 자연스럽게 이어 간다.
'장면을 담은 컷', '층층이 보여서', '시선이 오래 머물렀어요', '깊은 톤이 살아', '분위기를 자아내요'처럼 사진평·홍보글 문체를 나열하지 않는다.
한 사진당 의무적으로 2~4문장을 채우지 않는다. 비슷한 사진은 짧은 한 문장으로 이어도 된다.
사용자가 적은 '너무 좋았어', '예뻤어' 같은 감상은 똑같이 반복하지 말고 다정하고 생동감 있는 말투로 풀어 쓴다.
밝은 말투라면 ~더라고요, ~좋았어요, ~포인트!, ~담아봤어요처럼 문장 끝을 자연스럽게 섞고 가벼운 ㅎㅎ·ㅋㅋ도 적당히 쓴다.
사용자가 말하지 않은 동행인·여행 목적·일정·가격·서비스·주문·맛·향·재방문 계획을 새로 만들지 않는다.
밤 사진과 낮 사진이 섞여 있어도 하룻밤 묵었다·아침에 일어났다·객실로 올라왔다 같은 시간·동선을 추측하지 않는다.
동행인이 사진에 있다는 이유로 그 사람도 만족했다·좋아했다 같은 타인의 감상을 대신 만들지 않는다.
사진마다 제공한 photo_note를 해당 사진의 정답으로 따른다. 셀카 사진 옆에 욕실용품이나 온천 사진 설명을 붙이지 않는다.
사진 순서는 업로드 순서로 유지한다. 별도 사실(예: 욕실용품)은 관련 주제 문단이나 마무리에 자연스럽게 넣되 엉뚱한 사진의 설명으로 쓰지 않는다.
말투 예시: '온천이 정말 좋았다'는 경험은 '이번에 특히 좋았던 건 온천 ♨️\n좋았던 포인트라 따로 남겨봐요 ㅎㅎ'처럼 편하게 쓸 수 있다.
말투 예시: '욕실용품은 바이레도였다'는 사실은 '욕실에서 눈에 들어온 바이레도 어메니티 🧴\n이런 디테일도 기록해 두고 싶더라고요.'처럼 쓴다.
사진의 색·구도·표면·빛 반사를 평가하는 문장을 매 사진마다 붙이기보다 주어진 경험의 포인트를 짧고 말하듯 전한다.
감성 후기에서는 긴 소제목 대신 '♨️ 밤에 즐기는 온천', '🌊 객실에서 본 바다'처럼 짧은 이모지 소제목 2~4개를 쓸 수 있다.
밝고 자연스러운 말투·발랄한 말투·인스타 감성 말투라면 블로그에도 이모지를 적극 사용한다.
글 800~1600자 기준 6~12개 정도로 도입·소제목·좋았던 포인트·마무리에 나눠 쓰고 한 문장마다 붙이지 않는다.
예: 장소에는 📍, 온천에는 ♨️, 바다에는 🌊, 욕실 소품에는 🧴, 만족한 포인트에는 🤍 또는 ✨처럼 내용과 맞게 선택한다.
담백한 말투나 이모지 없이 쓰는 말투를 선택했다면 그 선택을 우선한다. 나이·성별·가족관계를 글에서 주장하지 않는다.
감성 후기는 한 줄 18~28자 안팎으로 의미가 끊기는 곳에서 직접 줄을 나누고 2~3줄 뒤 빈 줄로 숨을 고른다.
가격·주소·운영시간은 확인한 경우에만 작은 정보 문단으로 묶는다. 모르면 빼고 확인 필요 문구를 본문에 늘어놓지 않는다.
마무리는 실제로 좋았다고 한 포인트 1~2개로 짧게 끝낸다. '~기록으로 남기기', '사진마다 분위기가 달라 더 기억에 남았어요' 같은 틀에 박힌 요약은 피한다.
참고한 다른 블로그의 문장이나 개인 경험을 가져오지 말고 사용자의 메모와 사진으로 새롭게 작성한다."""

def mobile_lines(value,template="reference"):
    if template!="reference":return value
    wrapper=textwrap.TextWrapper(width=28,break_long_words=False,break_on_hyphens=False,replace_whitespace=False,drop_whitespace=True)
    lines=[]
    for line in value.replace("\r\n","\n").replace("\r","\n").split("\n"):
        if not line.strip():lines.append("")
        elif re.fullmatch(r"\s*\[\[photo:\d+\]\]\s*",line) or line.startswith("## "):lines.append(line.strip())
        else:lines.extend(wrapper.wrap(line.strip()) or [""])
    return "\n".join(lines).strip()


def photo_notes(prompt,count):
    """사용자가 1번/2번 사진에 붙인 설명을 각 이미지와 함께 전달한다."""
    notes=[""]*count
    matches=list(re.finditer(r"(?:([0-9]{1,2})\s*번(?!째)\s*(?:사진)?|사진\s*([0-9]{1,2})\s*번?)(?:은|는)?",prompt))
    for index,match in enumerate(matches):
        number=int(match.group(1) or match.group(2))
        end=matches[index+1].start() if index+1<len(matches) else len(prompt)
        if 1<=number<=count:notes[number-1]=prompt[match.end():end].strip(" ,.;\n")[:1000]
    return notes


LIVELY_TONES={"밝고 자연스러운 일상 후기체","친구에게 말하듯 발랄하게","친한 언니처럼 다정하게","밝고 경쾌한 인스타 감성으로","짧고 위트 있게"}

def polish_blog(draft,request,model,key,remote):
    """사진을 재전송하지 않는 짧은 문체 편집 단계. 새 사실을 추가하지 않는다."""
    import json
    count=len(request.get("images",[]))
    instructions="""너는 자연스럽고 센스 있는 한국어 여행·일상 블로그의 문장 편집자다.
목표는 젊고 밝은 여성 블로그에서 읽을 법한 편안한 해요체다. 나이·성별을 본문에 주장하지 않는다.
입력의 사진 메모·확인된 사실만 사용해 원고를 새롭게 다듬는다. 사진 자체는 입력되지 않으며 새 사실을 만들 수 없다.
원고에 있어도 메모에 없는 숙박일수·아침/밤 동선·남편의 만족감·피로 해소·추천 계획은 덜어낸다.
'~답니다', '~느껴졌어요', '~기억에 남았어요', '~여운', '분위기'를 반복하는 설명문을 줄인다.
'첫 사진은', '수면과 조명 색감', '객실 사진까지 보고 나니'처럼 사진을 분석·회고하는 문장을 쓰지 않는다.
좋았다고 한 포인트는 '여기서 특히 좋았던 건 온천 ♨️', '이건 따로 남기고 싶었어요 ㅎㅎ'처럼 짧고 말하듯 쓴다.
객실 셀카는 셀카 이야기로, 남편 온천 사진은 남편 사진 이야기로 연결한다. 다른 사람의 감정은 대신 쓰지 않는다.
이모지는 소제목에만 몰지 말고 본문의 문장 끝에도 적극 넣는다. 블로그 전체에 8~12개를 주제에 맞게 고른다.
이모지마다 빈 문단을 만들지 않고 '좋았던 포인트 🤍', '욕실용품은 바이레도 🧴'처럼 내용 옆에 자연스럽게 붙인다.
한 줄 18~28자, 2~3줄 단위의 여백. 짧은 소제목 2~4개는 ## 으로 쓴다.
분량을 억지로 늘리지 않는다. 받은 경험이 적으면 500~1000자여도 좋다. 사진마다 감상 4문장씩 채우지 않는다.
사진 위치 표시 [[photo:1]] 등은 모두 정확히 한 번씩 업로드 순서대로 유지한다.
다른 블로그 문장을 복사하지 않는다. URL과 출처 문법은 넣지 않는다.
JSON 객체 {"title":"...","blog":"..."} 하나만 반환한다. 제목은 장소명과 실제 포인트를 담아 자연스럽게 쓴다."""
    from channel_writing import language_guidance,threads_tone_guidance
    instructions+="\n함께 받은 instagram·threads도 각 채널의 목소리에 맞게 다듬어 같은 JSON에 반환한다. instagram은 1900자 이내, threads는 450자 이내로 작성한다.\n영어에서는 facts_translation도 의미를 바꾸지 않고 더 자연스럽게 고칠 수 있다. 필수 메모의 각 문장을 Instagram에 자연스럽게 한 번씩 포함하고 같은 뜻을 반복하는 다른 문장은 지운다.\nThreads는 블로그 소제목이나 해시태그 없이 하나의 짧은 관찰로 시작한다. 제공하지 않은 경험을 추가하지 않는다.\nJSON 키: title, blog, instagram, threads, facts_translation."
    instructions+="\n"+threads_tone_guidance(request.get("threads_tone","casual"),request.get("language","ko"))
    instructions+="\n"+language_guidance(request.get("language","ko"))
    if request.get("language")=="en":
        instructions="""You are a thoughtful native-English editor for personal social posts. Rewrite from the confirmed notes, not from the awkward wording of the draft.
The notes may be in Korean. Preserve their actual meaning, names, numbers and uncertainty. Add no invented companion, schedule, stress, sensation, return plan, or life lesson.
Use everyday spoken English, contractions where natural, and specific observations. Avoid travel-copy language, forced metaphors, 'it was enough', 'nothing dramatic', or an essay about slowing down.
Keep the amount of writing proportional to the notes: two simple facts usually need 2-4 sentences, not a long review. A short post is better than padded copy.
Blog: a natural title and a few short paragraphs. Preserve every [[photo:n]] marker exactly once in uploaded order. Short ## headings are optional, never compulsory.
Instagram: a short first line and a compact conversational paragraph, with 3-5 relevant hashtags only if useful. Do not repeat the same fact in the hook, body and ending.
Threads: one clear observation, 1-3 short conversational sentences, no title or hashtag list, 450 characters or fewer. It should sound like someone posting a thought, not presenting a review.
Render every confirmed-fact line faithfully in facts_translation. You may rephrase it naturally. Include each resulting sentence once, in context, in Instagram; remove overlapping sentences elsewhere.
Honor the chosen tone and emoji preference. Keep the prose uncomplicated; don't sound like a brochure or a literal translation.
Return only JSON with title, blog, instagram, threads, facts_translation. Title <=200 characters, Instagram <=1900, Threads <=450. No URLs or citation syntax in the prose."""
        instructions+="\n"+language_guidance("en")+"\n"+threads_tone_guidance(request.get("threads_tone","casual"),"en")
    from campaigns import CAMPAIGN_GUIDANCE,community_guidance,writing_context
    instructions+="\n"+community_guidance(request)
    if request.get("campaign_enabled"):instructions+="\n"+CAMPAIGN_GUIDANCE
    from places import PLACE_GUIDANCE
    instructions+="\n"+PLACE_GUIDANCE
    context={"selected_place":request.get("selected_place"),"verified_place_facts":request.get("verified_place_facts",[]),**writing_context(request),"language":request.get("language","ko"),"memo":request.get("prompt",""),"confirmed_facts":request.get("facts",""),"tone":request.get("tone",""),"writing_sample":request.get("style",""),"photo_notes":photo_notes(request.get("prompt",""),count),"photo_count":count,"draft":{"title":draft["title"],"blog":draft["blog"],"instagram":draft.get("instagram",""),"threads":draft.get("threads",""),"facts_translation":draft.get("facts_translation","")}}
    payload={"model":model,"instructions":instructions,"input":[{"role":"user","content":[{"type":"input_text","text":json.dumps(context,ensure_ascii=False)}]}],"max_output_tokens":4000,"store":False}
    if model.startswith("gpt-5"):payload["reasoning"]={"effort":"low"}
    response=remote("https://api.openai.com/v1/responses",payload,key)
    output="".join(part.get("text","") for item in response.get("output",[]) if item.get("type")=="message" for part in item.get("content",[]) if part.get("type")=="output_text")
    result=json.loads(output.strip())
    if not isinstance(result,dict) or not all(isinstance(result.get(name),str) and result[name].strip() for name in ("title","blog")):raise ValueError("다듬기 응답 형식이 맞지 않아요.")
    if len(result["title"])>200 or len(result["blog"])>30000:raise ValueError("다듬기 응답 길이가 맞지 않아요.")
    positions=[int(value) for value in re.findall(r"\[\[photo:(\d+)\]\]",result["blog"])]
    if positions!=list(range(1,count+1)):raise ValueError("다듬는 과정에서 사진 순서가 달라 원래 초안을 유지했어요.")
    refined={"title":result["title"],"blog":result["blog"]}
    for name,limit in (("instagram",2200),("threads",500),("facts_translation",4000)):
        if name in result:
            if not isinstance(result[name],str) or len(result[name])>limit or (name!="facts_translation" and not result[name].strip()):raise ValueError("다듬기 응답의 "+name+" 길이·형식이 맞지 않아요.")
            refined[name]=result[name]
    return refined,response.get("usage",{})
