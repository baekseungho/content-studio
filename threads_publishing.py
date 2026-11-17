"""Threads 공식 API 발행. 로그인 정보는 .env에서만 읽고 외부 발행은 명시적으로 요청할 때만 한다."""
import json
import os
import re
import sqlite3
import time
import uuid
from urllib.parse import urlsplit
from PIL import Image,ImageOps

SCHEMA="""
CREATE TABLE IF NOT EXISTS threads_attempts(id TEXT PRIMARY KEY,draft_id TEXT,state TEXT,result TEXT,created REAL);
CREATE UNIQUE INDEX IF NOT EXISTS threads_publish_guard ON threads_attempts(draft_id)
 WHERE state IN ('publishing','published','uncertain');
"""

class ThreadsPublisher:
 def __init__(self,remote,problem,db,get_draft,media,tunnel,media_base):
  self.remote,self.problem,self.db,self.get_draft=remote,problem,db,get_draft
  self.media,self.tunnel,self.media_base=media,tunnel,media_base
 def configuration(self):
  user=os.environ.get('THREADS_USER_ID','').strip()
  token=os.environ.get('THREADS_ACCESS_TOKEN','').strip()
  version=os.environ.get('THREADS_API_VERSION','v1.0').strip()
  missing=[key for key,value in [('THREADS_USER_ID',user),('THREADS_ACCESS_TOKEN',token)] if not value]
  invalid=[]
  if user and not re.fullmatch(r'[0-9]+',user):invalid.append('THREADS_USER_ID')
  if not re.fullmatch(r'v[0-9]+\.[0-9]+',version):invalid.append('THREADS_API_VERSION')
  try:
   url=urlsplit(self.media_base())
   media_ready=url.scheme=='https' and bool(url.hostname) and url.hostname not in ('localhost','127.0.0.1','::1') and not (url.username or url.password or url.query or url.fragment)
  except ValueError:media_ready=False
  return {'ready':not missing and not invalid,'missing':missing,'invalid':invalid,'media_ready':bool(media_ready),'temporary_connection':self.tunnel.active()}
 def graph(self,path,payload=None):
  config=self.configuration()
  if 'THREADS_ACCESS_TOKEN' in config['missing']:raise self.problem('실행 중인 앱에 Threads 토큰 설정이 없어요. .env의 THREADS_ACCESS_TOKEN을 저장한 뒤 앱을 완전히 종료하고 다시 실행해 주세요.',409)
  if 'THREADS_API_VERSION' in config['invalid']:raise self.problem('THREADS_API_VERSION 형식이 올바르지 않아요. .env에 v1.0으로 입력한 뒤 앱을 다시 실행해 주세요.',409)
  version=os.environ.get('THREADS_API_VERSION','v1.0').strip()
  return self.remote('https://graph.threads.com/'+version+'/'+path,payload,os.environ['THREADS_ACCESS_TOKEN'].strip(),60)
 def check(self):
  result=self.graph('me?fields=id,username')
  if not str(result.get('id','')).isdigit():raise self.problem('Threads 응답에서 계정 ID를 확인하지 못했어요.',502)
  matches=str(result.get('id',''))==os.environ.get('THREADS_USER_ID','').strip()
  return {'authenticated':True,'account_matches':matches,'user_id':str(result.get('id','')),'username':result.get('username',''),
   'message':'Threads 계정과 토큰을 확인했어요. 발행 권한은 실제 발행 시 확인돼요.' if matches else '토큰 인증은 됐지만 설정한 계정 ID가 없거나 달라요. 이 토큰의 Threads 계정 ID는 '+str(result.get('id','확인 불가'))+'예요. 본인 계정인지 확인하고 THREADS_USER_ID에 입력해 주세요.'}
 def wait_all(self,containers,progress):
  pending=set(containers);deadline=time.monotonic()+240;interval=5
  while pending:
   for cid in list(pending):
    result=self.graph(cid+'?fields=status,error_message');state=result.get('status')
    if state=='FINISHED':pending.remove(cid)
    elif state=='PUBLISHED':
     error=self.problem('이미 게시된 것으로 표시돼요. Threads 계정에서 결과를 확인해 주세요.',409);error.uncertain=True;raise error
    elif state in ('ERROR','EXPIRED'):raise self.problem('Threads 사진 처리가 실패했어요. 사진과 공개 연결을 확인해 주세요.',502)
    elif state!='IN_PROGRESS':raise self.problem('Threads 처리 상태를 확인하지 못했어요. 다시 발행하기 전에 계정을 확인해 주세요.',502)
   if not pending:return
   if time.monotonic()>=deadline:raise self.problem('Threads 사진 처리 시간이 초과됐어요. 공개 사진 연결을 확인해 주세요.',504)
   progress('Threads에서 사진을 처리하고 있어요. 잠시만 기다려 주세요.')
   time.sleep(min(interval,max(0,deadline-time.monotonic())));interval=min(60,interval*2)
 def publish(self,did,progress=lambda message:None,with_images=True):
  draft=self.get_draft(did);config=self.configuration()
  if not config['ready']:raise self.problem('Threads 계정을 먼저 연결해 주세요.',409)
  text=draft.get('threads','').strip()
  if not text or len(text)>500:raise self.problem('Threads 본문을 1~500자로 준비해 주세요.')
  images=draft.get('images',[]) if with_images else []
  if images and not config['media_ready']:raise self.problem('사진을 올리려면 사진 연결을 먼저 켜 주세요. 글만 발행할 때는 사진 연결이 필요 없어요.',409)
  for mid in images:
   if not (self.media/(mid+'.jpg')).is_file():raise self.problem('선택한 사진 파일이 없어요. 사진을 다시 추가해 주세요.')
  # Verify the token belongs to the explicitly configured account before public writes.
  connection=self.check()
  if not connection['account_matches']:raise self.problem(connection['message'],409)
  aid=uuid.uuid4().hex
  with self.db() as db:
   db.executescript(SCHEMA)
   try:db.execute('INSERT INTO threads_attempts VALUES(?,?,?,?,?)',(aid,did,'publishing','{}',time.time()))
   except sqlite3.IntegrityError:raise self.problem('이미 Threads에 발행했거나 결과 확인이 필요한 글이에요. 올린 글에서 기록을 확인해 주세요.',409)
  publish_started=False;container=None
  user=os.environ['THREADS_USER_ID'].strip()
  try:
   progress('Threads 발행을 준비하고 있어요.')
   if not images:
    container=self.graph(user+'/threads',{'media_type':'TEXT','text':text}).get('id')
    if not container:raise self.problem('Threads에서 글 준비 번호를 받지 못했어요.',502)
   else:
    children=[]
    for index,mid in enumerate(images):
     progress('사진 '+str(index+1)+'/'+str(len(images))+'장을 Threads에 전달하고 있어요.')
     with Image.open(self.media/(mid+'.jpg')) as image:
      ImageOps.pad(image.convert('RGB'),(1080,1350),color='#faf8f5').save(self.media/(mid+'-ig.jpg'),'JPEG',quality=90)
     if self.tunnel.active():self.tunnel.allow(mid)
     payload={'media_type':'IMAGE','image_url':self.media_base().rstrip('/')+'/media/'+mid+'-ig.jpg'}
     if len(images)>1:payload['is_carousel_item']=True
     else:payload['text']=text
     cid=self.graph(user+'/threads',payload).get('id')
     if not cid:raise self.problem('Threads에서 사진 준비 번호를 받지 못했어요.',502)
     children.append(str(cid))
    self.wait_all(children,progress)
    if len(children)>1:
     container=self.graph(user+'/threads',{'media_type':'CAROUSEL','children':','.join(children),'text':text}).get('id')
     if not container:raise self.problem('Threads에서 사진 묶음 준비 번호를 받지 못했어요.',502)
    else:container=children[0]
   self.wait_all([str(container)],progress)
   with self.db() as db:db.execute('UPDATE threads_attempts SET result=? WHERE id=?',(json.dumps({'container_id':container}),aid))
   progress('Threads에 발행하고 있어요. 완료 안내까지 기다려 주세요.')
   publish_started=True
   result=self.graph(user+'/threads_publish',{'creation_id':container})
   if not result.get('id'):raise self.problem('Threads 게시물 ID를 받지 못했어요.',502)
   with self.db() as db:db.execute("UPDATE threads_attempts SET state='published',result=? WHERE id=?",(json.dumps(result),aid))
   return {'state':'published','media_id':str(result['id'])}
  except Exception as error:
   uncertain=publish_started or getattr(error,'uncertain',False)
   with self.db() as db:db.execute('UPDATE threads_attempts SET state=? WHERE id=?',('uncertain' if uncertain else 'failed',aid))
   if uncertain:raise self.problem('Threads 발행 결과가 확실하지 않아요. 중복 발행을 막기 위해 다시 올리지 않았어요. Threads 계정에서 먼저 확인해 주세요.',502) from error
   raise
