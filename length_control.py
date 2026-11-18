"""Count using the publication checker and make at most one text-only repair."""
from collections import Counter
import json
import re
from campaigns import character_count,BLOG_MAX_CHARS

BLOG_FIELDS={"naver":"blog","tistory":"tistory"}

def limits(request):
    minimum=request.get("campaign_min_chars",0) if request.get("campaign_enabled") else 0
    maximum=request.get("campaign_max_chars",0) if request.get("campaign_enabled") else 0
    return min(minimum,BLOG_MAX_CHARS),min(maximum or BLOG_MAX_CHARS,BLOG_MAX_CHARS)


def violation(value,request):
    count=character_count(value,request.get("campaign_count_spaces",False))
    minimum,maximum=limits(request)
    return max(0,minimum-count)+max(0,count-maximum)


def statuses(generated,request,platforms,attempted=False,reason=""):
    minimum,maximum=limits(request)
    return [{"platform":p,"count":character_count(generated[field],request.get("campaign_count_spaces",False)),"minimum":minimum,"maximum":maximum,"satisfied":violation(generated[field],request)==0,"attempted":attempted,"reason":reason} for p,field in BLOG_FIELDS.items() if p in platforms]


def budget(platforms,request=None):
    minimum,maximum=limits(request or {})
    per_blog=min(max(2600,minimum*2+1000),maximum*2+1600,BLOG_MAX_CHARS*2+1000)
    return min(24000,700+sum(per_blog if p in BLOG_FIELDS else 1700 if p=="instagram" else 800 for p in platforms))


def planned_target(request):
    minimum,maximum=limits(request)
    if not minimum:return max(1,maximum-80)
    return min(minimum+max(250,minimum//4),maximum)


def length_instruction(request):
    minimum,maximum=limits(request)
    unit="including spaces but excluding line breaks" if request.get("campaign_count_spaces") else "excluding all whitespace"
    target=planned_target(request)
    aim=f"Aim near {target} counted characters" if minimum else f"Use only the length justified by the notes, safely below {maximum} counted characters; this is a ceiling, never a target"
    return f"FINAL BLOG LENGTH PRIORITY: Count actual characters, {unit}, excluding titles, hashtags and photo markers. Minimum={minimum or 'none'}, maximum={maximum}. {aim} in EACH requested blog. Never exceed the app's {BLOG_MAX_CHARS}-character body cap, even if user notes request a longer post. These numeric constraints override generic length suggestions. The style pass must preserve sufficient length. Expand distinct supplied facts, practical details and observations into connected paragraphs, without repetition or invented experience, menu, price, companion, hours or sensations. If evidence cannot support the requested minimum, return the strongest honest draft rather than fabricated filler. Leave room for the sponsorship notice inside the maximum. Never truncate mid-sentence."


def repeats_added(before,after):
    def parts(value):
        paragraphs=[re.sub(r"\s+","",p).casefold() for p in re.split(r"\n\s*\n|(?<=[.!?。])\s+",value)]
        return Counter(p for p in paragraphs if len(p)>=16)
    original=parts(before)
    return any(count>max(1,original[p]) for p,count in parts(after).items())

def repair_once(generated,request,platforms,context,model,key,remote,normalize,problem,progress):
    failed=[p for p,field in BLOG_FIELDS.items() if p in platforms and violation(generated[field],request)]
    if not failed:return generated,{},False,""
    progress("본문 길이를 확인했어요. 조건에 맞도록 현재 초안을 한 번 보완하고 있어요.",4)
    fields=[BLOG_FIELDS[p] for p in failed]
    details={}
    for field in fields:
        count=character_count(generated[field],request.get("campaign_count_spaces",False))
        short=count<limits(request)[0]
        details[field]={"current":count,"action":"expand" if short else "shorten","additional_characters_needed":max(0,planned_target(request)-count) if short else 0,"draft":generated[field]}
    instructions="""Edit only the supplied existing blog bodies to satisfy their actual character-count limits. Return only a JSON object with the supplied body field keys. Do not rewrite titles or other platforms. Use the existing draft, the user's concrete notes and verified facts only. No image bytes are supplied: never invent new visual details. Preserve the same factual claims and every [[photo:n]] marker in the same order. For an underlength draft, keep its existing sentences and paragraphs intact rather than summarizing or making them shorter. Add the requested additional_characters_needed as several distinct new paragraphs of useful explanation grounded in the supplied notes. Pick different concrete details for each new paragraph. Count those additions separately from the preserved original; returning a similar-length rewrite does not solve the task. Never add repeated sentences or generic padding. Do not invent tastes, visits, menu items, prices, companions or opening hours. If the facts cannot support more text, keep a truthful draft; do not pretend to meet the target. Shorten overlong drafts without dropping mandatory facts or cutting sentences. Preserve the language and natural voice. Do not add URLs, Korean in an English draft, or instructions to the user inside the post."""
    instructions+="\n"+length_instruction(request)+"\nRequired language: "+request.get("language","ko")+". JSON keys: "+json.dumps(fields)
    payload={"model":model,"instructions":instructions,"input":[{"role":"user","content":[{"type":"input_text","text":json.dumps({"confirmed_context":context,"bodies":details},ensure_ascii=False)}]}],"max_output_tokens":budget(failed,request),"store":False}
    if model.startswith("gpt-5"):payload["reasoning"]={"effort":"low"}
    usage={};reason=""
    try:
        response=remote("https://api.openai.com/v1/responses",payload,key);usage=response.get("usage",{})
        output="".join(part.get("text","") for item in response.get("output",[]) if item.get("type")=="message" for part in item.get("content",[]) if part.get("type")=="output_text")
        candidate=json.loads(re.sub(r"^```(?:json)?\s*|\s*```$","",output.strip()))
        if not isinstance(candidate,dict):raise ValueError("형식 확인 필요")
        chosen=dict(generated)
        for field in fields:
            value=candidate.get(field)
            if not isinstance(value,str) or not value.strip() or len(value)>30000:continue
            if re.findall(r"\[\[photo:\d+\]\]",value)!=re.findall(r"\[\[photo:\d+\]\]",generated[field]):continue
            if request.get("language")=="en" and re.search(r"[가-힣]",value):continue
            value=normalize(value)
            if repeats_added(generated[field],value):continue
            if violation(value,request)<violation(generated[field],request):chosen[field]=value
        generated=chosen
    except (problem,ValueError,TypeError):reason="분량 보완을 마치지 못해 현재 초안을 유지했어요."
    if any(violation(generated[BLOG_FIELDS[p]],request) for p in failed):
        short=any(character_count(generated[BLOG_FIELDS[p]],request.get("campaign_count_spaces",False))<limits(request)[0] for p in failed)
        reason=reason or ("한 번 보완했지만 분량 조건을 충족하지 못했어요. 먹은 메뉴·구체적인 장단점·이용 과정·사진 설명 등 실제 경험을 더 적은 뒤 이 초안에서 이어서 보완해 주세요." if short else "한 번 보완했지만 최대 분량을 넘어요. 덜 중요한 설명을 줄이거나 이 초안에서 다시 분량을 맞춰 주세요.")
    return generated,usage,True,reason
