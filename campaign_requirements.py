"""Confirmed campaign metadata, conflicts and honest manual-check status."""
import hashlib
import json
import re
from campaign_brief import digest,FIELDS

def _text(value,limit):
    if not isinstance(value,str) or len(value)>limit:raise ValueError('체험단 조건의 형식 또는 길이를 확인해 주세요.')
    return value

def read_meta(body):
    manual=body.get('campaign_manual_checks',[])
    if not isinstance(manual,list) or len(manual)>20:raise ValueError('직접 확인할 조건은 20개까지 남길 수 있어요.')
    clean=[];seen=set()
    for item in manual:
        if not isinstance(item,dict) or not isinstance(item.get('id'),str) or not re.fullmatch(r'[a-f0-9]{20}',item['id']):raise ValueError('직접 확인할 조건을 다시 정리해 주세요.')
        if item['id'] in seen:continue
        seen.add(item['id']);clean.append({'id':item['id'],'text':_text(item.get('text',''),600),'quote':_text(item.get('quote',''),1000)})
    review=body.get('campaign_brief_review',{})
    if not isinstance(review,dict):raise ValueError('안내문 확인 정보를 다시 불러와 주세요.')
    reviewed=review.get('hash','')
    if not isinstance(reviewed,str) or reviewed and not re.fullmatch(r'[a-f0-9]{64}',reviewed):raise ValueError('안내문 확인 정보를 다시 불러와 주세요.')
    sources=review.get('sources',[])
    if not isinstance(sources,list) or len(sources)>60:raise ValueError('확인한 조건이 너무 많아요.')
    normalized=[]
    for item in sources:
        if not isinstance(item,dict) or not isinstance(item.get('field'),str) or item['field'] not in FIELDS:raise ValueError('조건의 원문 정보를 확인해 주세요.')
        value=item.get('value')
        if type(value) not in (str,int,bool) or isinstance(value,str) and len(value)>2000:raise ValueError('조건 값을 확인해 주세요.')
        if type(item.get('edited',False)) is not bool:raise ValueError('수정한 조건의 원문 정보를 확인해 주세요.')
        normalized.append({'field':item['field'],'value':value,'quote':_text(item.get('quote',''),1000),'edited':item.get('edited',False)})
    states=body.get('campaign_manual_state',{})
    if not isinstance(states,dict) or any(p not in ('naver','tistory') for p in states):raise ValueError('미션 확인 상태를 다시 불러와 주세요.')
    checked={}
    for platform,items in states.items():
        if not isinstance(items,dict) or len(items)>20 or any(k not in seen or not isinstance(v,str) or not re.fullmatch(r'[a-f0-9]{64}',v) for k,v in items.items()):raise ValueError('미션 확인 상태를 다시 확인해 주세요.')
        checked[platform]=dict(items)
    notes=body.get('campaign_experience',{})
    if not isinstance(notes,dict) or any(k not in ('process','good','caution') for k in notes):raise ValueError('추가 경험 메모를 확인해 주세요.')
    return {'campaign_manual_checks':clean,'campaign_brief_review':{'hash':reviewed,'sources':normalized},'campaign_manual_state':checked,'campaign_experience':{k:_text(v,600) for k,v in notes.items()}}

def preflight(body):
    if not body.get('campaign_enabled'):return []
    from campaigns import keywords,character_count,count_keyword,read_fields,TEXT_FIELDS
    issues=[]
    def add(code,field,message,level='error',related=None):issues.append({'code':code,'field':field,'message':message,'level':level,'related_fields':related or []})
    for field in [*TEXT_FIELDS,"keyword_min_count","campaign_min_chars","campaign_max_chars","campaign_min_photos","campaign_count_spaces"]:
        if field not in body:continue
        try:read_fields({field:body[field]})
        except ValueError as error:add('campaign_field_format',field,str(error))
    minimum=body.get('campaign_min_chars',0);maximum=body.get('campaign_max_chars',0)
    if type(minimum) is int and type(maximum) is int:
        if not 0<=minimum<=5000 or not 0<=maximum<=5000:add('campaign_length_range','campaign_min_chars','본문 조건은 0~5,000자 안에서 정해 주세요.')
        elif maximum and minimum>maximum:add('campaign_length_conflict','campaign_min_chars',f'최소 {minimum:,}자가 최대 {maximum:,}자보다 커요. 업체 안내의 분량을 다시 확인해 주세요.',related=['campaign_max_chars'])
        limit=maximum or 5000
        longest=max([character_count(x,body.get('campaign_count_spaces',False)) for x in str(body.get('required_phrases','')).splitlines()]+[0])
        if longest>limit:add('campaign_phrase_too_long','required_phrases',f'필수 문구 하나가 본문 최대 {limit:,}자보다 길어요. 두 조건을 함께 지킬 수 없어요.',related=['campaign_max_chars'])
    forbidden=keywords(str(body.get('campaign_forbidden','')))
    if body.get('disclosure','none')!='none':
        from writing_quality import DISCLOSURES,DISCLOSURES_EN
        notice=(DISCLOSURES_EN if body.get('language')=='en' else DISCLOSURES).get(body.get('disclosure'),'')
        overlap=next((word for word in forbidden if count_keyword(notice,word)),None)
        if overlap:add('campaign_disclosure_forbidden','campaign_forbidden',f'선택한 제공 안내에 ‘{overlap}’가 들어가요. 실제 제공 내용을 숨기지 않도록 업체와 금지 표현을 확인해 주세요.',related=['disclosure'])
    for field in ('campaign_brand','title_keywords','body_keywords','required_phrases'):
        required=str(body.get(field,''))
        overlap=next((word for word in forbidden if count_keyword(required,word)),None)
        if overlap:add('campaign_forbidden_conflict',field,f'‘{overlap}’를 꼭 넣는 조건과 쓰지 않는 조건이 함께 있어요. 업체와 확인한 조건 하나로 정리해 주세요.',related=['campaign_forbidden'])
    if body.get('disclosure','none')!='none' and re.search(r'내돈내산|직접\s*(?:구매|결제)',str(body.get('required_phrases',''))):add('campaign_disclosure_conflict','required_phrases','제공받은 후기와 직접 구매했다는 필수 문구가 서로 달라요. 실제 받은 내용에 맞춰 확인해 주세요.',related=['disclosure'])
    review=body.get('campaign_brief_review',{})
    if isinstance(review,dict) and review.get('hash') and review['hash']!=digest(str(body.get('campaign_brief',''))):add('campaign_brief_changed','campaign_brief','업체 안내문이 바뀌었어요. 다시 정리하거나 현재 입력한 조건을 확인해 주세요.')
    if body.get('disclosure','none')=='none':add('campaign_disclosure_pending','disclosure','어떤 내용을 제공받았는지 선택해 주세요. 초안은 먼저 만들 수 있어요.','warning')
    if body.get('language')=='en' and re.search(r'[가-힣]',str(body.get('title_keywords',''))+str(body.get('body_keywords',''))+str(body.get('required_phrases',''))):add('campaign_language_review','language','영문 글에 넣을 필수 키워드·문구의 영문 표기를 업체와 확인해 주세요.','warning')
    return issues

def report(body,platform='naver'):
    from campaigns import read_fields,mission_checks
    from platform_writing import view
    meta=read_meta(body);candidate=view({**body,**meta},platform)
    issues=preflight(candidate)
    errors=[i for i in issues if i['level']=='error']
    fields={}
    try:fields=read_fields(candidate)
    except ValueError as error:
        if not errors:issues.append({'code':'campaign_fields','field':'campaign_brand','message':str(error),'level':'error','related_fields':[]})
        checks=[]
    else:checks=mission_checks({**candidate,**fields}) if not errors else []
    content={k:candidate.get(k) for k in ('title','blog','images','disclosure','campaign_brief','language')};content.update({k:fields.get(k,candidate.get(k)) for k in FIELDS});content["campaign_brief"]=digest(str(candidate.get("campaign_brief","")));content['manual']=meta['campaign_manual_checks']
    fingerprint=hashlib.sha256(json.dumps(content,ensure_ascii=False,sort_keys=True).encode()).hexdigest()
    manual=[{**item,'checked':meta['campaign_manual_state'].get(platform,{}).get(item['id'])==fingerprint} for item in meta['campaign_manual_checks']]
    from writing_quality import review as review_quality
    quality=review_quality({**candidate,**fields,'review_channel':'blog'}) if fields and not errors else [{'level':x['level'],'message':x['message'],'field':x['field']} for x in issues]
    return {'quality_checks':quality,'checks':checks,'preflight':issues,'manual':manual,'fingerprint':fingerprint,'brief_hash':digest(str(body.get('campaign_brief','')))}
