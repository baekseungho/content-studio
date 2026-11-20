"""Local final-delivery inspection. Never calls a model, connects a tunnel or publishes."""
import copy,math,re
from PIL import Image,UnidentifiedImageError
from platform_writing import view,LABELS
from content_rules import clean_blog
from campaigns import character_count
from writing_quality import publication_errors
from writing_templates import template_for


def snapshot(draft,body,required=False):
    if required or 'updated' in body:
        expected=body.get('updated')
        if type(expected) not in (int,float) or not math.isfinite(expected):raise ValueError('확인할 원고의 저장 버전을 다시 선택해 주세요.')
        if expected!=draft.get('updated'):raise FileExistsError('다른 창에서 원고가 바뀌어 전달하지 않았어요. 현재 원고를 새 이야기로 보관하거나 최신 저장 글을 열고 다시 확인해 주세요.')
    return copy.deepcopy(draft)


def inspect(draft,platform,media,with_images=True,target_url=''):
    if platform not in LABELS:raise ValueError('전달할 채널을 선택해 주세요.')
    if type(with_images) is not bool:raise ValueError('사진 포함 여부를 확인해 주세요.')
    candidate=view(draft,platform)
    if platform=='threads' and not with_images:
        candidate['threads_include_images']=False;candidate['images']=[]
    blog=platform in ('naver','tistory')
    text=clean_blog(candidate.get('blog','')) if blog else candidate.get(platform,'')
    checks=publication_errors(candidate,platform)
    if blog and not candidate.get('title','').strip():checks.append({'level':'error','field':'title','message':'블로그 제목을 먼저 적어 주세요.'})
    if not text.strip():checks.append({'level':'error','field':'body','message':'전달할 본문을 먼저 적어 주세요.'})
    photos=[]
    for index,mid in enumerate(candidate.get('images',[])):
        photo={'id':mid,'number':index+1,'available':False,'width':0,'height':0}
        try:
            if not isinstance(mid,str) or not re.fullmatch(r'[a-f0-9]{32}',mid):raise ValueError()
            with Image.open(media/(mid+'.jpg')) as image:
                photo.update(width=image.width,height=image.height);image.load()
            photo['available']=True
        except (OSError,ValueError,UnidentifiedImageError,Image.DecompressionBombError):
            checks.append({'level':'error','field':'photos','photo_number':index+1,'message':str(index+1)+'번 사진을 읽을 수 없어요. 원고의 사진을 다시 선택해 주세요.'})
        photos.append(photo)
    if platform=='instagram' and not photos:checks.append({'level':'error','field':'photos','message':'인스타그램에 올릴 사진을 한 장 이상 골라 주세요.'})
    formatting=template_for(candidate.get('template')) if blog else None
    return {'id':draft['id'],'updated':draft['updated'],'platform':platform,'label':LABELS[platform],
            'title':candidate.get('title','') if blog else '', 'text':text,'photos':photos,
            'text_chars':character_count(text,True) if blog else len(text),'format':formatting,
            'language':candidate.get('language','ko'),'target_url':target_url,
            'with_images':bool(photos),'checks':checks,'ready':not any(c['level']=='error' for c in checks),
            'effect':'editor' if blog else 'public',
            'notice':'글과 사진을 편집기에 입력해요. 입력된 사진·정렬·글꼴을 확인한 뒤 블로그에서 직접 발행해 주세요.' if blog else '확인한 글과 선택한 사진을 연결된 계정에 공개 발행해요.'}
