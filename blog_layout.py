"""Deterministic blog reflow, never a writing/model operation."""
import re
import textwrap

PRESETS={"manual":{"width":28,"lines":3},"notes":{"width":20,"lines":2},"comfort":{"width":28,"lines":3},"review":{"width":40,"lines":5}}

def settings(value=None):
    value={} if value is None else value
    if not isinstance(value,dict):raise ValueError("줄바꿈 설정을 다시 골라 주세요.")
    preset=value.get("preset","manual")
    if not isinstance(preset,str) or preset not in (*PRESETS,"custom"):raise ValueError("줄바꿈 스타일을 다시 골라 주세요.")
    defaults=PRESETS.get(preset,PRESETS["comfort"])
    result={"preset":preset}
    for key,low,high in (("width",16,44),("lines",2,6)):
        number=value.get(key,defaults[key])
        if type(number) is not int or not low<=number<=high:raise ValueError("한 줄은 16~44자, 문단은 2~6줄 사이로 골라 주세요.")
        result[key]=number
    return result

def all_settings(value=None):
    if value is None:return {}
    if not isinstance(value,dict) or any(key not in ("naver","tistory") for key in value):raise ValueError("블로그별 줄바꿈 설정을 확인해 주세요.")
    return {key:settings(item) for key,item in value.items()}

def text_map(value=None):
    if value is None:return {}
    if not isinstance(value,dict) or any(key not in ("naver","tistory") or not isinstance(item,str) or len(item)>30000 for key,item in value.items()):raise ValueError("줄바꿈 원고를 읽지 못했어요. 현재 글을 다시 확인해 주세요.")
    return dict(value)

def protected(line):
    return bool(re.match(r"^(?:##\s|\[\[photo:\d+\]\]$|#[^\s#]+(?:\s+#[^\s#]+)*$|[-*•]\s|\d+[.)]\s|[^:：]{1,18}[:：])",line))

def reflow(value,option=None,language="ko"):
    config=settings(option)
    if config["preset"]=="manual":return value
    width=config["width"]*(2 if language=="en" else 1)
    wrap=textwrap.TextWrapper(width=width,break_long_words=False,break_on_hyphens=False,replace_whitespace=False,drop_whitespace=True)
    result=[]
    for block in re.split(r"\n\s*\n",value.replace("\r\n","\n").replace("\r","\n").strip()):
        lines=[]
        def flush():
            if not lines:return
            wrapped=wrap.wrap(" ".join(lines))
            result.extend("\n".join(wrapped[i:i+config["lines"]]) for i in range(0,len(wrapped),config["lines"]))
            lines.clear()
        for line in block.splitlines():
            line=line.strip()
            if not line:continue
            if protected(line):flush();result.append(line)
            else:lines.append(line)
        flush()
    result="\n\n".join(result)
    if len(result)>30000:raise ValueError("줄바꿈을 넣으면 본문이 30,000자를 넘어요. 원고를 조금 줄인 뒤 다시 적용해 주세요.")
    return result
