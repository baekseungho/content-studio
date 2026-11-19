"""Reusable preferences only; never copy visits, benefits, old prose or publication state."""
import json,time,uuid,re
from campaigns import read_fields,tags_from
from campaign_requirements import preflight
from places import selected_place

FIELDS=('title_keywords','body_keywords','hashtags','campaign_forbidden','keyword_min_count','campaign_min_chars','campaign_max_chars','campaign_min_photos','campaign_count_spaces')
SCHEMA="CREATE TABLE IF NOT EXISTS reusable_kits(id TEXT PRIMARY KEY,name TEXT,kind TEXT,settings TEXT,revision INTEGER,updated REAL,archived INTEGER NOT NULL DEFAULT 0)"


def settings(kind,value):
 if not isinstance(value,dict):raise ValueError("다시 쓸 설정을 확인해 주세요.")
 allowed={'brand':('campaign_brand','selected_place'),'tags':('hashtags',),'campaign':FIELDS}
 if kind not in allowed or any(key not in allowed[kind] for key in value):raise ValueError("경험·제공 내역·기한·원고는 재사용 묶음에 저장하지 않아요. 다시 쓸 설정만 골라 주세요.")
 if kind=='brand':
  brand=value.get('campaign_brand','')
  if not isinstance(brand,str) or len(brand)>150:raise ValueError("업체·제품 이름은 150자 이내로 적어 주세요.")
  place=selected_place(value.get('selected_place'))
  if not brand.strip() and not place:raise ValueError("기억할 업체 이름이나 장소를 먼저 적어 주세요.")
  return {'campaign_brand':brand.strip(),'selected_place':place}
 if kind=='tags':
  raw=value.get('hashtags','')
  if not isinstance(raw,str) or len(raw)>1500:raise ValueError("태그를 다시 확인해 주세요.")
  tags=tags_from(raw)
  if not tags:raise ValueError("기억할 태그를 먼저 적어 주세요.")
  return {'hashtags':' '.join('#'+tag for tag in tags)}
 clean=read_fields({**value,'campaign_enabled':True})
 conflicts=[p['message'] for p in preflight(clean) if p['level']=='error']
 if conflicts:raise ValueError("조건을 먼저 정리해 주세요: "+conflicts[0])
 if not any(clean[key] for key in ('title_keywords','body_keywords','hashtags','campaign_forbidden','campaign_min_chars','campaign_max_chars','campaign_min_photos','campaign_count_spaces')) and clean['keyword_min_count']==1:raise ValueError('기억할 키워드나 미션 조건을 먼저 적어 주세요.')
 return {key:clean[key] for key in FIELDS}


def read_row(row):return {'id':row['id'],'name':row['name'],'kind':row['kind'],'settings':json.loads(row['settings']),'revision':row['revision'],'updated':row['updated'],'archived':bool(row['archived'])}


def list_kits(db,archived=False):
 with db() as conn:
  conn.execute(SCHEMA);return [read_row(row) for row in conn.execute('SELECT * FROM reusable_kits WHERE archived=? ORDER BY updated DESC,id',(int(archived),))]


def save(db,body):
 name=body.get('name');kind=body.get('kind');did=body.get('id');revision=body.get('revision',0)
 if not isinstance(name,str) or not 1<=len(name.strip())<=60:raise ValueError("묶음 이름을 1~60자로 적어 주세요.")
 if type(revision) is not int or revision<0:raise ValueError("저장한 묶음을 다시 열어 주세요.")
 clean=settings(kind,body.get('settings'));created=did is None
 if created:did=uuid.uuid4().hex
 elif not isinstance(did,str) or not re.fullmatch(r'[a-f0-9]{32}',did):raise ValueError("묶음 번호를 확인해 주세요.")
 with db() as conn:
  conn.execute(SCHEMA);old=conn.execute('SELECT * FROM reusable_kits WHERE id=?',(did,)).fetchone()
  if not created and not old:raise LookupError("저장한 묶음을 찾지 못했어요.")
  if (not old and revision!=0) or (old and old['revision']!=revision):raise FileExistsError("다른 창에서 묶음이 바뀌었어요. 다시 불러온 뒤 수정해 주세요.")
  if (not old or old['archived']) and conn.execute('SELECT COUNT(*) FROM reusable_kits WHERE archived=0').fetchone()[0]>=60:raise ValueError("묶음은 60개까지 보관할 수 있어요. 사용하지 않는 묶음을 먼저 정리해 주세요.")
  stamp=time.time();changed=conn.execute('INSERT INTO reusable_kits VALUES(?,?,?,?,?,?,0) ON CONFLICT(id) DO UPDATE SET name=excluded.name,kind=excluded.kind,settings=excluded.settings,revision=excluded.revision,updated=excluded.updated,archived=0 WHERE reusable_kits.revision=?',(did,name.strip(),kind,json.dumps(clean,ensure_ascii=False),revision+1,stamp,revision))
  if changed.rowcount!=1:raise FileExistsError("다른 창에서 묶음이 바뀌었어요. 최신 설정을 다시 열어 주세요.")
 return {'id':did,'name':name.strip(),'kind':kind,'settings':clean,'revision':revision+1,'updated':stamp,'archived':False}


def archive(db,body):
 did=body.get('id');revision=body.get('revision')
 if not isinstance(did,str) or not re.fullmatch(r'[a-f0-9]{32}',did) or type(revision) is not int:raise ValueError("정리할 묶음을 확인해 주세요.")
 with db() as conn:
  conn.execute(SCHEMA);changed=conn.execute('UPDATE reusable_kits SET archived=1,revision=revision+1,updated=? WHERE id=? AND revision=?',(time.time(),did,revision))
  if changed.rowcount!=1:raise FileExistsError("묶음이 바뀌었어요. 목록을 다시 불러와 주세요.")
 return {'archived':True,'id':did,'revision':revision+1}


GROUPS={'brand':{'brand':('campaign_brand',),'place':('selected_place',)},'tags':{'tags':('hashtags',)},'campaign':{'keywords':('title_keywords','body_keywords','keyword_min_count'),'length':('campaign_min_chars','campaign_max_chars','campaign_count_spaces'),'photos':('campaign_min_photos',),'tags':('hashtags',),'forbidden':('campaign_forbidden',)}}


def preview(db,body):
 did=body.get('id');revision=body.get('revision');current=body.get('current',{});groups=body.get('groups',[]);mode=body.get('tag_mode','append')
 if not isinstance(did,str) or not re.fullmatch(r'[a-f0-9]{32}',did) or type(revision) is not int:raise ValueError('불러올 묶음을 다시 골라 주세요.')
 with db() as conn:
  conn.execute(SCHEMA);row=conn.execute('SELECT * FROM reusable_kits WHERE id=? AND archived=0',(did,)).fetchone()
 if not row:raise LookupError('불러올 묶음을 찾지 못했어요.')
 kit=read_row(row);kind=kit['kind']
 if kit['revision']!=revision:raise FileExistsError('다른 창에서 묶음이 바뀌었어요. 목록에서 다시 골라 주세요.')
 if not isinstance(groups,list) or not groups or len(groups)>5 or any(not isinstance(g,str) or g not in GROUPS[kind] for g in groups) or len(set(groups))!=len(groups) or mode not in ('append','replace'):raise ValueError('불러올 항목을 하나 이상 골라 주세요.')
 allowed=set(key for group in GROUPS[kind].values() for key in group)
 if kind=='campaign':allowed.add('campaign_enabled')
 if not isinstance(current,dict) or any(key not in allowed for key in current):raise ValueError('현재 설정을 다시 확인해 주세요.')
 if 'place' in groups and kit['settings'].get('selected_place') and body.get('place_confirmed') is not True:raise ValueError('이번에도 같은 장소·지점·주소인지 확인해 주세요.')
 if kind=='campaign' and body.get('conditions_confirmed') is not True:raise ValueError('이번 업체 안내에도 같은 조건인지 확인해 주세요.')
 patch={key:kit['settings'][key] for group in groups for key in GROUPS[kind][group]}
 if 'hashtags' in patch:
  old=current.get('hashtags','')
  if not isinstance(old,str) or len(old)>1500:raise ValueError('현재 태그를 먼저 확인해 주세요.')
  tags=tags_from((old+' ' if mode=='append' else '')+patch['hashtags']);patch['hashtags']=' '.join('#'+tag for tag in tags)
 if kind=='campaign':
  merged=read_fields({**current,**patch,'campaign_enabled':True});errors=[item['message'] for item in preflight(merged) if item['level']=='error']
  if errors:raise ValueError('기존 조건과 함께 확인해 주세요: '+errors[0])
  patch={key:merged[key] for key in patch};patch['campaign_enabled']=True
 elif kind=='brand':
  if 'campaign_brand' in patch:patch['campaign_brand']=read_fields({'campaign_brand':patch['campaign_brand']})['campaign_brand']
  if 'selected_place' in patch:patch['selected_place']=selected_place(patch['selected_place'])
 changes=[{'field':key,'before':current.get(key),'after':value} for key,value in patch.items() if current.get(key)!=value]
 return {'patch':patch,'changes':changes,'warnings':['선택한 설정만 바꿔요. 기존 원고·사진·경험 메모는 유지해요.','제공 내역·방문일·정확한 필수 문구·기한은 이번 안내에서 새로 확인해 주세요.']}
