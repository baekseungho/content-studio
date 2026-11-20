"""Honest library states and explicit per-revision review; never publish from here."""
import hashlib,json,math,re,sqlite3,time
import publication_records

CHANNELS={"naver":"blog","tistory":"tistory","instagram":"instagram","threads":"threads"}
SCHEMA="""
CREATE TABLE IF NOT EXISTS library_meta(draft_id TEXT PRIMARY KEY,label TEXT NOT NULL DEFAULT '',starred INTEGER NOT NULL DEFAULT 0,archived INTEGER NOT NULL DEFAULT 0,last_opened REAL NOT NULL DEFAULT 0,revision INTEGER NOT NULL DEFAULT 0);
CREATE TABLE IF NOT EXISTS story_reviews(draft_id TEXT,platform TEXT,fingerprint TEXT,created REAL,PRIMARY KEY(draft_id,platform));
CREATE TABLE IF NOT EXISTS publish_snapshots(attempt_id TEXT PRIMARY KEY,draft_id TEXT,platform TEXT,fingerprint TEXT,created REAL);
CREATE TABLE IF NOT EXISTS handoff_events(id TEXT PRIMARY KEY,draft_id TEXT,platform TEXT,fingerprint TEXT,state TEXT,photo_count INTEGER,created REAL);
"""

def ensure(conn):
 # execute separately: executescript would implicitly commit a publication transaction.
 for statement in SCHEMA.split(';'):
  if statement.strip():conn.execute(statement)


def identity(value):
 if not isinstance(value,str) or not re.fullmatch(r"[a-f0-9]{32}",value):raise ValueError("이야기 번호를 확인해 주세요.")
 return value


def fingerprint(draft,platform):
 from platform_writing import view
 if platform not in CHANNELS:raise ValueError("확인할 채널을 골라 주세요.")
 projected=view(draft,platform);blog=platform in ("naver","tistory")
 value={"platform":platform,"body":projected.get("blog" if blog else platform,""),"title":projected.get("title","") if blog else "","images":projected.get("images",[]),"language":projected.get("language","ko"),"disclosure":projected.get("disclosure","none"),"facts":projected.get("facts",""),"place":draft.get("selected_place"),"brand":draft.get("campaign_brand","")}
 if blog:
  from campaigns import TEXT_FIELDS
  NUMBER_FIELDS=("keyword_min_count","campaign_min_chars","campaign_max_chars","campaign_min_photos")
  value.update({key:draft.get(key) for key in (*TEXT_FIELDS,*NUMBER_FIELDS,"campaign_enabled","campaign_count_spaces","campaign_manual_checks")})
  value["manual_state"]=draft.get("campaign_manual_state",{}).get(platform,{})
  value["template"]=projected.get("template","reference")
 else:
  value["media"]=projected.get("channel_media",{}).get(platform) if value["images"] else None
  if platform=="instagram":value.update({key:draft.get(key,"") for key in ("facts_translation","facts_translation_source")})
 return hashlib.sha256(json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(",",":")).encode()).hexdigest()


def record_publish(conn,attempt_id,draft,platform):
 ensure(conn);conn.execute("INSERT INTO publish_snapshots VALUES(?,?,?,?,?)",(attempt_id,draft['id'],platform,fingerprint(draft,platform),time.time()))


def record_handoff(db,platform,token,item,state,count):
 with db() as conn:
  ensure(conn);conn.execute("INSERT OR IGNORE INTO handoff_events VALUES(?,?,?,?,?,?,?)",(hashlib.sha256(token.encode()).hexdigest(),item['id'],platform,item.get('fingerprint',''),state,count if type(count) is int else None,time.time()))


def metadata(row=None):
 return {"label":row['label'] if row else "","starred":bool(row['starred']) if row else False,"archived":bool(row['archived']) if row else False,"last_opened":row['last_opened'] if row else 0,"revision":row['revision'] if row else 0}


def update_meta(db,body):
 did=identity(body.get('id'));revision=body.get('revision');changes=body.get('changes')
 if type(revision) is not int or revision<0 or not isinstance(changes,dict) or not changes or any(k not in ('label','starred','archived') for k in changes):raise ValueError("이야기 표시 설정을 확인해 주세요.")
 for key,value in changes.items():
  if key=='label':
   if not isinstance(value,str) or len(value)>80:raise ValueError("이야기 이름은 80자 이내로 적어 주세요.")
  elif type(value) is not bool:raise ValueError("즐겨찾기·보관 설정을 다시 골라 주세요.")
 with db() as conn:
  ensure(conn)
  if not conn.execute('SELECT id FROM drafts WHERE id=?',(did,)).fetchone():raise LookupError("이야기를 찾지 못했어요.")
  old=metadata(conn.execute('SELECT * FROM library_meta WHERE draft_id=?',(did,)).fetchone());value={**old,**changes};value['label']=value['label'].strip()
  changed=conn.execute("INSERT INTO library_meta(draft_id,label,starred,archived,last_opened,revision) VALUES(?,?,?,?,?,?) ON CONFLICT(draft_id) DO UPDATE SET label=excluded.label,starred=excluded.starred,archived=excluded.archived,revision=excluded.revision WHERE library_meta.revision=?",(did,value['label'],int(value['starred']),int(value['archived']),old['last_opened'],revision+1,revision))
  if old['revision']!=revision or changed.rowcount!=1:raise FileExistsError("다른 창에서 이야기 표시가 바뀌었어요. 목록을 새로 불러온 뒤 다시 골라 주세요.")
  return {**value,'revision':revision+1}


def opened(db,did):
 did=identity(did)
 with db() as conn:
  ensure(conn)
  if not conn.execute('SELECT id FROM drafts WHERE id=?',(did,)).fetchone():raise LookupError("이야기를 찾지 못했어요.")
  stamp=time.time();conn.execute('INSERT INTO library_meta(draft_id,last_opened) VALUES(?,?) ON CONFLICT(draft_id) DO UPDATE SET last_opened=excluded.last_opened',(did,stamp));return {'opened':stamp}


def mark_review(db,body):
 from platform_writing import migrate,view
 from writing_quality import publication_errors
 from campaign_requirements import report
 did=identity(body.get('id'));platform=body.get('platform');expected=body.get('updated')
 if platform not in CHANNELS or body.get('confirmed') is not True:raise ValueError("원고를 직접 확인한 뒤 완료를 눌러 주세요.")
 if type(expected) not in (int,float) or not math.isfinite(expected):raise ValueError("저장한 원고를 다시 확인해 주세요.")
 with db() as conn:
  ensure(conn);row=conn.execute('SELECT data,updated FROM drafts WHERE id=?',(did,)).fetchone()
  if not row:raise LookupError("이야기를 찾지 못했어요.")
  if row['updated']!=expected:raise FileExistsError("다른 창에서 원고가 바뀌었어요. 최신 저장 글을 열고 다시 확인해 주세요.")
  draft=migrate(json.loads(row['data']));candidate=view(draft,platform);field='blog' if platform in ('naver','tistory') else platform
  if not candidate.get(field,'').strip():raise ValueError("이 채널의 원고를 먼저 적어 주세요.")
  errors=publication_errors(draft,platform)
  if platform=='instagram' and not candidate.get('images'):raise ValueError("인스타그램에 올릴 사진을 먼저 골라 주세요.")
  if errors:raise ValueError("먼저 원고를 수정해 주세요: "+errors[0]['message'])
  if platform in ('naver','tistory') and draft.get('campaign_enabled'):
   checked=report(draft,platform)
   if any(not item['checked'] for item in checked['manual']):raise ValueError("체험단의 직접 확인 항목을 먼저 확인해 주세요.")
  fp=fingerprint(draft,platform);created=time.time()
  result=conn.execute('INSERT INTO story_reviews(draft_id,platform,fingerprint,created) SELECT id,?,?,? FROM drafts WHERE id=? AND updated=? ON CONFLICT(draft_id,platform) DO UPDATE SET fingerprint=excluded.fingerprint,created=excluded.created',(platform,fp,created,did,expected))
  if result.rowcount!=1:raise FileExistsError("확인 중 원고가 바뀌었어요. 최신 저장 글을 다시 열어 주세요.")
  return {'confirmed':True,'platform':platform,'fingerprint':fp,'created':created,'updated':expected}


def _attempts(conn):
 tables={row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")};result={}
 for table,platform in (('attempts','instagram'),('threads_attempts','threads')):
  if table not in tables:continue
  for row in conn.execute(f'SELECT a.id,a.draft_id,a.state,a.created,s.fingerprint FROM {table} a LEFT JOIN publish_snapshots s ON s.attempt_id=a.id ORDER BY a.created DESC'):
   key=(row['draft_id'],platform)
   # Existing duplicate-publication guards also apply after an edit; do not hide them behind a later failed attempt.
   old=result.get(key)
   if old is None or (old['state']=='failed' and row['state'] in ('published','uncertain','publishing')):result[key]=dict(row)
 return result


def channel_states(draft,reviews,attempts,handoffs,legacy=(),publications=None):
 from platform_writing import migrate,view
 draft=migrate(dict(draft));selected=draft.get('selected_platforms',[]);states={};publications=publications or {}
 def attach(state,record,same):
  state.update(state='published' if same else 'changed',label='발행 확인 · 직접 기록' if same else '이전 원고 발행 · 직접 기록',published_url=record['url'],record_id=record['id'],record_revision=record['revision'],recorded_at=record['created'],verification='user_confirmed')
 for platform,field in CHANNELS.items():
  has=bool(str(draft.get(field,'')).strip())
  if not has and platform not in selected and platform not in attempts and platform not in handoffs and platform not in legacy and platform not in publications:continue
  if not has:
   event=attempts.get(platform)
   if event:states[platform]={'state':'changed' if event['state']=='published' else 'attention','label':'이전 발행 기록 · 현재 원고 없음' if event['state']=='published' else '발행 결과 확인 필요 · 현재 원고 없음','reviewed':False}
   elif platform in handoffs or platform in legacy:states[platform]={'state':'changed','label':'이전 편집기 입력 · 현재 원고 없음','reviewed':False}
   else:states[platform]={'state':'idea','label':'아직 작성 전','reviewed':False}
   if platform in publications:
    attach(states[platform],publications[platform],False);states[platform]['label']='이전 발행 기록 · 현재 원고 없음'
   continue
  fp=fingerprint(draft,platform);review=reviews.get(platform);confirmed=bool(review and review['fingerprint']==fp)
  state={'state':'ready' if confirmed else 'draft','label':'원고 확인 완료' if confirmed else '원고 검토 전','reviewed':confirmed}
  event=attempts.get(platform)
  if event:
   same=event.get('fingerprint')==fp;status=event['state']
   if status in ('publishing','uncertain'):state.update(state='attention',label='발행 결과 확인 필요')
   elif status=='published':state.update(state='published' if same else 'changed',label='발행 완료' if same else '이전 발행 기록 · 현재 원고 재확인')
   elif status=='failed':state.update(state='attention',label='발행 실패 기록 · 확인 필요')
  elif platform in handoffs:
   event=handoffs[platform];same=event['fingerprint']==fp
   if same:state.update(state='handed_off' if event['state']=='ready' else 'attention',label={'ready':'편집기 입력 완료 · 발행 직접 확인','partial':'편집기 서식 확인 필요','failed':'편집기 전달 실패','blocked':'계정 인증 확인 필요'}[event['state']])
   else:state.update(state='changed',label='이전 편집기 입력 · 원고 변경됨')
  elif platform in legacy:state['label']+=' · 이전 편집기 입력 기록'
  if platform in publications:attach(state,publications[platform],publications[platform]['fingerprint']==fp)
  states[platform]=state
 return states


def page(db,summary,params=None,only_id=None,legacy_handoffs=None):
 params=params or {};query=params.get('q','');platform=params.get('platform','');state=params.get('state','');sort=params.get('sort','updated');scope=params.get('scope','active')
 if not isinstance(query,str) or len(query)>200 or platform not in ('',*CHANNELS) or state not in ('','idea','draft','ready','published','attention') or sort not in ('updated','opened','name') or scope not in ('active','starred','archived'):raise ValueError("내 글의 검색 조건을 다시 골라 주세요.")
 try:offset=int(params.get('offset',0));limit=int(params.get('limit',24))
 except (ValueError,TypeError):raise ValueError("목록의 페이지를 다시 열어 주세요.")
 if not 0<=offset<=1000000 or not 1<=limit<=48:raise ValueError("목록의 페이지를 다시 열어 주세요.")
 with db() as conn:
  ensure(conn);rows=conn.execute('SELECT id,title,data,updated FROM drafts'+(' WHERE id=?' if only_id else '')+' ORDER BY updated DESC', (only_id,) if only_id else ()).fetchall();metas={row['draft_id']:metadata(row) for row in conn.execute('SELECT * FROM library_meta')};reviews={};handoffs={}
  for row in conn.execute('SELECT * FROM story_reviews'):reviews.setdefault(row['draft_id'],{})[row['platform']]=dict(row)
  for row in conn.execute('SELECT * FROM handoff_events ORDER BY created DESC'):handoffs.setdefault(row['draft_id'],{}).setdefault(row['platform'],dict(row))
  attempts=_attempts(conn);publications=publication_records.latest(conn)
 items=[];counts={'active':0,'starred':0,'archived':0}
 for row in rows:
  meta=metas.get(row['id'],metadata());counts['archived' if meta['archived'] else 'active']+=1
  if meta['starred'] and not meta['archived']:counts['starred']+=1
  if only_id is None and (meta['archived']!=(scope=='archived') or (scope=='starred' and not meta['starred'])):continue
  try:
   data=json.loads(row['data'])
   if not isinstance(data,dict):raise ValueError()
   card=summary(row);card['channel_states']=channel_states(data,reviews.get(row['id'],{}),{p:attempts[(row['id'],p)] for p in CHANNELS if (row['id'],p) in attempts},handoffs.get(row['id'],{}),{p for p,ids in (legacy_handoffs or {}).items() if row['id'] in ids},publications.get(row['id'],{}))
  except (ValueError,TypeError,KeyError,AttributeError):
   data={};card={'id':row['id'],'title':str(row['title'] or '읽기 확인이 필요한 이야기')[:200],'updated':row['updated'],'excerpt':'저장한 이야기 형식을 확인해야 해요. 원본은 그대로 보관했어요.','titles':[],'platforms':[],'thumbnail':'','photo_count':0,'place':'','channel_states':{},'damaged':True}
  card['meta']=meta;card['story_title']=meta['label'] or card['title']
  if platform and platform not in card['channel_states']:continue
  values=card['channel_states'].values()
  aggregate='attention' if card.get('damaged') or any(v['state'] in ('attention','changed') for v in values) else 'idea' if not any(v['state']!='idea' for v in values) else 'published' if all(v['state']=='published' for v in values) else 'ready' if any(v['state'] in ('ready','handed_off') for v in values) else 'draft'
  card['state']=aggregate
  target_state=card['channel_states'].get(platform,{}).get('state') if platform else aggregate
  if state and (target_state not in ('attention','changed') if state=='attention' else target_state not in ('ready','handed_off') if state=='ready' else target_state!=state):continue
  if query.strip().casefold() not in ' '.join([card['story_title'],*card['titles'],card['excerpt'],card['place'],str(data.get('campaign_brand','')),str(data.get('prompt','')),str(data.get('facts',''))]).casefold():continue
  # Select the actual first photo of the last channel, including a photo no longer in the prepared pool.
  current=data.get('editing_platform') or next(iter(card['channel_states']),'naver')
  try:
   from platform_writing import view
   image_list=view(data,current).get('images',[]);first=next((mid for mid in image_list if isinstance(mid,str) and re.fullmatch(r'[a-f0-9]{32}',mid)),None)
   card['thumbnail']=first or ''
   card['photo_count']=len(image_list)
  except (ValueError,TypeError,KeyError):pass
  card['workspace_step']=data.get('workspace_step',1);items.append(card)
 items.sort(key=(lambda c:(not c['meta']['starred'],-(c['meta']['last_opened'] or c['updated']))) if sort=='opened' else (lambda c:(not c['meta']['starred'],c['story_title'].casefold())) if sort=='name' else (lambda c:(not c['meta']['starred'],-c['updated'])))
 return {'items':items[offset:offset+limit],'total':len(items),'offset':offset,'limit':limit,'has_more':offset+limit<len(items),'counts':counts}


def story_card(db,summary,did,legacy_handoffs=None):
 identity(did);result=page(db,summary,only_id=did,legacy_handoffs=legacy_handoffs)
 if not result['items']:raise LookupError("이야기를 찾지 못했어요.")
 return result['items'][0]


# Small in-memory thumbnails keep reopening/filtering a photo-heavy library light.
# They are served only by the local app, never registered with the public gateway.
from functools import lru_cache
from pathlib import Path
import io
from PIL import Image,ImageOps

@lru_cache(maxsize=64)
def _thumbnail(path,stamp,size):
 with Image.open(path) as source:
  image=ImageOps.pad(ImageOps.exif_transpose(source).convert('RGB'),(200,200),method=Image.Resampling.LANCZOS,color='#faf8f5')
  output=io.BytesIO();image.save(output,'JPEG',quality=80);return output.getvalue()


def thumbnail(media,mid):
 identity(mid);source=Path(media)/(mid+'.jpg');stat=source.stat();return _thumbnail(str(source.resolve()),stat.st_mtime_ns,stat.st_size)
