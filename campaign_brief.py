"""Conservative, local-only extraction of merchant instructions with exact evidence."""
import hashlib
import json
import re

NUMBER=r"(?:\d[\d,]*(?:\.\d+)?\s*천(?:\s*\d+(?:\s*백)?)?|\d[\d,]*(?:\.\d+)?\s*백|\d[\d,]*)"
FIELDS={"campaign_brand","campaign_benefit","title_keywords","body_keywords","required_phrases","hashtags","campaign_forbidden","keyword_min_count","campaign_min_chars","campaign_max_chars","campaign_min_photos","campaign_count_spaces"}
LIMITS={"keyword_min_count":5,"campaign_min_chars":5000,"campaign_max_chars":5000,"campaign_min_photos":10}
LABELS={"campaign_brand":"업체·제품 이름","campaign_benefit":"제공 내역","title_keywords":"제목 키워드","body_keywords":"본문 키워드","required_phrases":"그대로 넣을 문구","hashtags":"블로그 태그","campaign_forbidden":"사용하지 않을 표현","keyword_min_count":"본문 키워드 최소 횟수","campaign_min_chars":"본문 최소 글자 수","campaign_max_chars":"본문 최대 글자 수","campaign_min_photos":"최소 사진 수","campaign_count_spaces":"글자 수 계산 기준"}

def digest(brief):return hashlib.sha256(brief.strip().encode()).hexdigest()

def number(value):
    value=re.sub(r"[,\s]","",value)
    if '천' in value:
        first,tail=value.split('천');return int(float(first)*1000)+(int(tail[:-1])*100 if tail.endswith('백') else int(tail) if tail else 0)
    if value.endswith('백'):return int(float(value[:-1])*100)
    return int(value)

def extract(brief):
    if not isinstance(brief,str) or len(brief)>5000:raise ValueError('업체 안내문은 5,000자 이내로 붙여 주세요.')
    if not brief.strip():raise ValueError('업체에서 받은 안내문을 먼저 붙여 주세요.')
    rows=[];seen=set();scope='blog';truncated=False
    def add(field,value,quote,start,kind='condition',reason=''):
        nonlocal truncated
        if not quote.strip():return
        quote=quote[:1000]
        if kind=="manual":value=str(value)[:600]
        key=(field,json.dumps(value,ensure_ascii=False),quote,kind)
        if key in seen:return
        if len(rows)>=60:truncated=True;return
        seen.add(key)
        if field in LIMITS and (type(value) is not int or value>LIMITS[field] or value<0 or field=='campaign_max_chars' and value==0):
            kind='manual';reason='앱에서 자동으로 맞출 수 있는 범위를 넘어요. 업체와 확인하거나 최종 편집기에서 직접 맞춰 주세요.'
        identity=hashlib.sha256(json.dumps(key,ensure_ascii=False).encode()).hexdigest()[:20]
        rows.append({'id':identity,'field':field,'value':value,'label':LABELS.get(field,'직접 확인할 조건'),'kind':kind,'quote':quote,'start':start,'end':start+len(quote),'line':brief.count('\n',0,start)+1,'reason':reason})
    lines=list(re.finditer(r'[^\r\n]+',brief))
    for i,match in enumerate(lines):
        line=match[0].strip();start=match.start()+len(match[0])-len(match[0].lstrip());handled=False;literal=False;keyword_line=False
        if not line:continue
        other=bool(re.search(r'인스타(?:그램)?|스레드|Threads|릴스|유튜브',line,re.I));blog=bool(re.search(r'네이버|블로그|티스토리',line))
        if re.fullmatch(r'[\[【#\s]*(?:인스타그램|인스타|스레드|Threads|릴스)(?:\s*(?:미션|조건|안내))?[\]】\s:：]*',line,re.I):scope='other'
        elif re.fullmatch(r'[\[【#\s]*(?:네이버\s*)?(?:블로그|티스토리)(?:\s*(?:미션|조건|안내))?[\]】\s:：]*',line):scope='blog'
        if other or scope=='other' and not blog:
            add('',line, line,start,'manual','다른 채널의 조건일 수 있어요. 블로그 조건으로 자동 적용하지 않았어요.');continue
        # Explicit labelled lists; an unlabeled choice is never guessed.
        labels=[(r'(?:업체|매장|제품|브랜드)\s*(?:명|이름)','campaign_brand'),(r'제공\s*(?:내역|내용|품목)','campaign_benefit'),(r'(?:제목|타이틀)\s*(?:필수\s*)?키워드','title_keywords'),(r'본문\s*(?:필수\s*)?키워드','body_keywords'),(r'(?:필수\s*)?(?:해시태그|태그)','hashtags'),(r'(?:필수\s*문구|필수\s*문장|그대로\s*넣을\s*문구)','required_phrases'),(r'(?:금지\s*(?:표현|문구|단어)|사용\s*금지(?:\s*표현)?)','campaign_forbidden')]
        for pattern,field in labels:
            found=re.match(r'^[\s\-*•\d.)]*(?:'+pattern+r')\s*[:：]\s*(.*)$',line)
            if not found:continue
            quote=line;value=found[1].strip()
            if not value and i+1<len(lines) and not re.search(r'[:：]',lines[i+1][0]):
                value=lines[i+1][0].strip();quote=brief[start:lines[i+1].end()]
            if not value:continue
            handled=True;literal=field in ('required_phrases','campaign_brand','campaign_benefit','campaign_forbidden');keyword_line=field in ('title_keywords','body_keywords','hashtags')
            if field in ('title_keywords','body_keywords','hashtags','required_phrases') and re.search(r'중\s*(?:한|하나|\d)|택\s*\d|선택|또는|혹은|\bor\b',value,re.I):
                add('',line,quote,start,'manual','여러 항목 중 고르는 조건이에요. 사용할 키워드를 직접 골라 적어 주세요.');continue
            if re.search(r'https?://|내돈내산|제공받|협찬|원고료|광고비',value) and field=='required_phrases':
                add('',line,quote,start,'manual','제공 표시·링크·사실에 관한 문구예요. 받은 내용과 맞는지 직접 확인해 주세요.');continue
            if field in ('title_keywords','body_keywords'):
                value=re.sub(r'\(?\s*(?:각|각각|정확히|최소|최대)?\s*\d+\s*(?:회|번)\s*(?:이상|이하|이내|미만|씩)?\s*\)?','',value)
                value=re.sub(r'(?:[을를]\s+|\s+)(?:꼭|반드시)?\s*(?:포함(?:\s|해|하|할|되|$)|삽입(?:\s|해|하|할|$)|사용(?:\s|해|하|할|$)|넣어).*$','',value).strip(' ,')
            value=value.strip(' "\'“”‘’')
            if value:add(field,value,quote,start,reason='실제 경험과 맞는 문구인지 확인해 주세요.' if field=='required_phrases' else '')
        if literal:continue
        if not keyword_line and re.search(r'[0-9,.]+\s*만',line) and re.search(r'글자|자',line):add('',line,line,start,'manual','앱의 5,000자 범위를 넘는 분량일 수 있어요. 업체와 조건을 확인해 주세요.');continue
        title_length=bool(re.search(r'제목|타이틀',line) and re.search(NUMBER+r'\s*(?:글자|자)',line))
        if title_length:add('',line,line,start,'manual','제목 길이는 본문 분량에 섞지 않고 직접 확인해 주세요.');continue
        # Length ranges must be handled as one range, never as a single maximum.
        ranges=list(re.finditer(r'('+NUMBER+r')\s*(?:자|글자)?\s*[~〜～\-–]\s*('+NUMBER+r')\s*(?:자|글자)',line))
        for m in ranges:
            add('campaign_min_chars',number(m[1]),line,start);add('campaign_max_chars',number(m[2]),line,start);handled=True
        if not ranges:
            found=list(re.finditer(r'('+NUMBER+r')\s*(?:글자|자)\s*(이상|초과|넘게|이하|이내|미만)',line))
            for m in found:
                minimum=m[2] in ('이상','초과','넘게');value=number(m[1])+(1 if m[2] in ('초과','넘게') else -1 if m[2]=='미만' else 0)
                add('campaign_min_chars' if minimum else 'campaign_max_chars',value,line,start);handled=True
            if not found:
                for m in re.finditer(r'(최소|최대)\s*('+NUMBER+r')\s*(?:글자|자)',line):add('campaign_min_chars' if m[1]=='최소' else 'campaign_max_chars',number(m[2]),line,start);handled=True
        if re.search(r'(?:자|글자|분량)',line) and re.search(r'공백\s*(?:포함|제외|미포함)',line):
            add('campaign_count_spaces',not bool(re.search(r'공백\s*(?:제외|미포함)',line)),line,start);handled=True
        if not keyword_line and re.search(r'사진|이미지',line):
            span=re.search(r'(\d+)\s*(?:장|컷|매)?\s*[~〜～\-–]\s*(\d+)\s*(?:장|컷|매)',line)
            if span:
                if int(span[1])>int(span[2]):add('',line,line,start,'manual','사진 수 범위가 서로 맞지 않아요. 업체와 확인해 주세요.')
                else:
                    add('campaign_min_photos',int(span[1]),line,start)
                    if int(span[2])<10:add('',line,line,start,'manual','사진 최대 '+span[2]+'장도 최종 원고에서 직접 확인해 주세요.')
                handled=True;continue
            photos=re.search(r'(?:최소\s*)?(\d+)\s*(?:장|컷|매)\s*(이상|이내|이하|미만)?',line)
            if photos:
                if photos[2] in ('이내','이하','미만'):add('',line,line,start,'manual','사진 최대 수 조건은 최종 원고에서도 직접 확인해 주세요.')
                else:add('campaign_min_photos',int(photos[1]),line,start)
                handled=True
        if re.search(r'본문|키워드',line):
            count=re.search(r'(?:각|각각)?\s*(\d+)\s*(?:회|번)\s*(이상|씩|정확히)?',line)
            if count:
                if re.search(r'정확히|이하|이내|미만|각각[^\d]*\d+회.+\d+회',line):add('',line,line,start,'manual','키워드마다 다른 횟수나 정확한 횟수는 직접 확인해 주세요.')
                else:add('keyword_min_count',int(count[1]),line,start)
                handled=True
        if not handled and re.fullmatch(r'(?:#[\w]+[\s,]*)+',line):add('hashtags',line,line,start);handled=True
        if not handled and re.search(r'\d{1,2}[./]\d{1,2}.*까지|\d{1,2}월\s*\d+일|지도|배너|링크|https?://|동영상|영상|마감|기한|예약|가격|금액|광고|협찬|공정위|내돈내산|필수|금지|키워드|제공|글자|분량|단어|\bwords?\b|사진|제목',line):
            add('',line,line,start,'manual','자동 확인이 어려운 조건이에요. 업체 안내와 최종 게시 화면에서 확인해 주세요.')
    return {'version':1,'brief_hash':digest(brief),'suggestions':rows,'truncated':truncated,'notice':'항목이 많아 일부만 정리했어요. 남은 조건은 원문에서 확인해 주세요.' if truncated else '원문과 비교한 뒤 선택한 항목만 반영해요. 빠진 조건은 직접 추가할 수 있어요.'}
