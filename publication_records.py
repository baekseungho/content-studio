"""User-confirmed blog publication links. No remote fetching or automatic publication claims."""
import json,math,re,time,uuid
from urllib.parse import urlsplit,parse_qs,unquote,quote

SCHEMA="""
CREATE TABLE IF NOT EXISTS publication_records(id TEXT PRIMARY KEY,draft_id TEXT NOT NULL,platform TEXT NOT NULL,url TEXT NOT NULL,fingerprint TEXT NOT NULL,title TEXT NOT NULL,created REAL NOT NULL,updated REAL NOT NULL,archived INTEGER NOT NULL DEFAULT 0,revision INTEGER NOT NULL DEFAULT 1,UNIQUE(draft_id,platform,url,fingerprint));
CREATE INDEX IF NOT EXISTS publication_story ON publication_records(draft_id,platform,archived,updated);
"""

def ensure(conn):
 for statement in SCHEMA.split(';'):
  if statement.strip():conn.execute(statement)

def identity(value):
 if not isinstance(value,str) or not re.fullmatch(r'[a-f0-9]{32}',value):raise ValueError('이야기 또는 발행 기록을 다시 선택해 주세요.')
 return value

def canonical_url(value,platform,naver_blog_id='',blog_url=''):
 message='발행된 게시물의 공개 주소를 복사해 주세요. 글쓰기·관리·미리보기 주소는 기록할 수 없어요.'
 if platform not in ('naver','tistory') or not isinstance(value,str) or not 1<=len(value)<=2048 or not isinstance(blog_url,str) or re.search(r'[\x00-\x1f\x7f\\]',value.strip()):raise ValueError(message)
 try:
  parsed=urlsplit(value.strip());host=(parsed.hostname or '').lower();query=parse_qs(parsed.query,keep_blank_values=True)
  if parsed.scheme!='https' or parsed.username or parsed.password or parsed.port or parsed.netloc.lower()!=host:raise ValueError()
  if any(k.casefold() in ('secret','preview','previewmode','token','access_token','password') for k in query):raise ValueError()
  if platform=='naver':
   if host not in ('blog.naver.com','m.blog.naver.com'):raise ValueError()
   match=re.fullmatch(r'/([a-zA-Z0-9_-]{1,64})/([1-9][0-9]{0,19})/?',parsed.path)
   if match:owner,number=match.groups()
   elif parsed.path=='/PostView.naver' and len(query.get('blogId',[]))==len(query.get('logNo',[]))==1:
    owner,number=query['blogId'][0],query['logNo'][0]
    if not re.fullmatch(r'[a-zA-Z0-9_-]{1,64}',owner) or not re.fullmatch(r'[1-9][0-9]{0,19}',number):raise ValueError()
   else:raise ValueError()
   if naver_blog_id and owner.casefold()!=naver_blog_id.casefold():raise ValueError('현재 연결한 네이버 블로그의 게시물 주소를 넣어 주세요. 다른 블로그 주소예요.')
   return 'https://blog.naver.com/'+owner+'/'+number
  if not re.fullmatch(r'[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.tistory\.com',host) or host in ('www.tistory.com','notice.tistory.com'):raise ValueError()
  if blog_url and urlsplit(blog_url).hostname!=host:raise ValueError('현재 선택한 티스토리와 다른 블로그 주소예요. 글을 올린 블로그를 다시 확인해 주세요.')
  if re.search(r'%(?![a-fA-F0-9]{2})',parsed.path):raise ValueError()
  path=unquote(parsed.path,errors='strict').rstrip('/')
  if re.fullmatch(r'/[1-9][0-9]{0,19}',path):return 'https://'+host+path
  match=re.fullmatch(r'/entry/([^/]+)',path)
  if not match or not match[1].strip() or match[1] in ('.','..') or re.search(r'[\x00-\x1f\x7f\\]',path):raise ValueError()
  result='https://'+host+'/entry/'+quote(match[1],safe='-._~')
  if len(result)>2048:raise ValueError()
  return result
 except (ValueError,UnicodeError) as error:
  if str(error).startswith(('현재 연결한','현재 선택한')):raise
  raise ValueError(message) from None

def public(row):
 value=dict(row);value['url']=canonical_url(value['url'],value['platform']);value['archived']=bool(value['archived']);value['verification']='user_confirmed';return value

def save(db,body,naver_blog_id=''):
 from platform_writing import view,migrate
 from story_library import fingerprint
 did=identity(body.get('id'));platform=body.get('platform');expected=body.get('updated')
 if body.get('confirmed') is not True:raise ValueError('게시물을 직접 열어 이 원고로 발행한 글이 맞는지 확인해 주세요.')
 if type(expected) not in (int,float) or not math.isfinite(expected):raise ValueError('저장한 원고의 버전을 다시 확인해 주세요.')
 url=canonical_url(body.get('url'),platform,naver_blog_id,body.get('blog_url',''))
 with db() as conn:
  conn.execute('BEGIN IMMEDIATE');ensure(conn);row=conn.execute('SELECT data,updated FROM drafts WHERE id=?',(did,)).fetchone()
  if not row:raise LookupError('이야기를 찾지 못했어요.')
  if row['updated']!=expected:raise FileExistsError('다른 창에서 원고가 바뀌었어요. 현재 저장 글을 다시 읽고 게시물 주소를 기록해 주세요.')
  try:draft=migrate(json.loads(row['data']));candidate=view(draft,platform);body_text=candidate.get('blog','')
  except (TypeError,KeyError,ValueError,AttributeError):raise ValueError('저장 원고를 읽지 못했어요. 원본을 확인해 주세요.') from None
  if not isinstance(body_text,str) or not body_text.strip():raise ValueError('이 채널의 원고를 먼저 보관해 주세요.')
  fp=fingerprint(draft,platform);old=conn.execute('SELECT * FROM publication_records WHERE draft_id=? AND platform=? AND url=? AND fingerprint=?',(did,platform,url,fp)).fetchone();stamp=time.time()
  if old:
   if old['archived']:conn.execute('UPDATE publication_records SET archived=0,revision=revision+1,updated=? WHERE id=?',(stamp,old['id']))
   return public(conn.execute('SELECT * FROM publication_records WHERE id=?',(old['id'],)).fetchone())
  if conn.execute('SELECT count(*) FROM publication_records WHERE draft_id=?',(did,)).fetchone()[0]>=100:raise ValueError('이 이야기에는 발행 기록을 100개까지 보관해요. 새 이야기에 이어서 기록해 주세요.')
  rid=uuid.uuid4().hex;conn.execute('INSERT INTO publication_records(id,draft_id,platform,url,fingerprint,title,created,updated) VALUES(?,?,?,?,?,?,?,?)',(rid,did,platform,url,fp,candidate.get('title','')[:200],stamp,stamp))
  return public(conn.execute('SELECT * FROM publication_records WHERE id=?',(rid,)).fetchone())

def archive(db,body):
 rid=identity(body.get('record_id'));revision=body.get('revision');archived=body.get('archived')
 if type(revision) is not int or revision<1 or type(archived) is not bool:raise ValueError('기록 상태를 다시 확인해 주세요.')
 with db() as conn:
  ensure(conn);updated=conn.execute('UPDATE publication_records SET archived=?,revision=revision+1,updated=? WHERE id=? AND revision=?',(int(archived),time.time(),rid,revision))
  if updated.rowcount!=1:raise FileExistsError('다른 창에서 기록이 바뀌었어요. 목록을 다시 열어 주세요.')
  return public(conn.execute('SELECT * FROM publication_records WHERE id=?',(rid,)).fetchone())

def rows(db,did=None,archived=False):
 if did is not None:identity(did)
 from story_library import fingerprint
 result=[]
 with db() as conn:
  ensure(conn);records=conn.execute('SELECT p.*,d.data FROM publication_records p JOIN drafts d ON d.id=p.draft_id WHERE p.archived=?'+(' AND p.draft_id=?' if did else '')+' ORDER BY p.updated DESC,p.rowid DESC LIMIT 100',(int(archived),did) if did else (int(archived),)).fetchall()
  for row in records:
   try:value=public({k:row[k] for k in row.keys() if k!='data'})
   except (ValueError,TypeError,KeyError,AttributeError):continue
   try:value['matches_current']=fingerprint(json.loads(row['data']),row['platform'])==row['fingerprint']
   except (ValueError,TypeError,KeyError,AttributeError):value.update(matches_current=False,draft_unreadable=True)
   result.append(value)
 return result

def latest(conn):
 ensure(conn);result={}
 for row in conn.execute('SELECT * FROM publication_records WHERE archived=0 ORDER BY updated DESC,rowid DESC'):
  try:value=public(row)
  except (ValueError,TypeError,KeyError):continue
  result.setdefault(row['draft_id'],{}).setdefault(row['platform'],value)
 return result
