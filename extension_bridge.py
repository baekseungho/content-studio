"""한 번만 사용할 수 있는 로컬 초안 전달 코드. 키·쿠키는 포함하지 않는다."""
import base64
import json
import secrets
import threading
import time
from content_rules import clean_blog
from platform_writing import view as platform_view
from campaigns import mission_checks
from writing_quality import publication_errors
from writing_templates import template_for

class HandoffError(Exception):
    def __init__(self,message,status=400):
        self.message,self.status=message,status

class ExtensionBridge:
    def __init__(self,media,guard,channel="naver",record_report=None):
        self.record_report=record_report
        self.channel=channel
        self.media=media
        self.guard=guard
        self.lock=threading.RLock()
        self.tickets={}
        self.reports={}
        self.receipts={}
    def prune(self):
        now=time.time()
        self.tickets={k:v for k,v in self.tickets.items() if v["expires"]>now}
        self.reports={k:v for k,v in self.reports.items() if v["expires"]>now}
        self.receipts={k:v for k,v in self.receipts.items() if v["expires"]>now}
    def create(self,draft,allow_repeat=False,writer_url=None):
        draft=platform_view(draft,self.channel)
        with self.lock:
            self.prune()
            missing=[check["label"] for check in mission_checks(draft) if not check["passed"]]
            if missing:raise HandoffError("체험단 미션을 먼저 확인해 주세요: "+", ".join(missing[:4]),409)
            errors=publication_errors(draft,self.channel)
            if errors:raise HandoffError("원고를 먼저 확인해 주세요: "+" · ".join(item["message"] for item in errors[:3]),409)
            if self.guard.status()["blocked"]:
                raise HandoffError("네이버 보호 잠금 상태예요. 공식 네이버에서 직접 제한 해제와 정상 로그인을 확인해 주세요.",409)
            if draft["id"] in self.guard.read().get("completed",[]) and not allow_repeat:
                raise HandoffError("이 초안은 이전에 편집기에 입력됐어요. 다시 시험하려면 ‘같은 글 다시 넣기’를 선택하고 빈 글쓰기 화면을 사용해 주세요.",409)
            if any(item["id"]==draft["id"] for item in self.reports.values()):
                raise HandoffError("이 글은 편집기에 전달 중이거나 결과 기록을 기다리고 있어요. 확장에서 ‘결과 확인·기록 다시 보내기’를 먼저 눌러 주세요. 글은 다시 넣지 않아요.",409)
            # 같은 초안에서 새 번호를 요청하면 사용하지 않은 옛 번호만 교체한다.
            self.tickets={key:value for key,value in self.tickets.items() if value["draft"]["id"]!=draft["id"]}
            if len(self.tickets)>=5:
                raise HandoffError("전달 코드가 여러 개 준비되어 있어요. 기존 코드를 사용하거나 10분 뒤 새로 만들어 주세요.",409)
            for mid in draft["images"]:
                if not (self.media/(mid+".jpg")).is_file():
                    raise HandoffError("선택한 사진 파일이 없어요. 사진을 다시 추가해 주세요.")
            code=secrets.token_urlsafe(24)
            self.tickets[code]={"draft":draft,"writer_url":writer_url,"allow_repeat":allow_repeat is True,"expires":time.time()+600}
            return {"code":code,"expires_in":600,"photo_count":len(draft["images"]),"title":draft["title"]}
    def inspect(self,code):
        with self.lock:
            self.prune();item=self.tickets.get(code)
            if not item:raise HandoffError("전달 코드가 만료되었거나 사용됐어요. 앱에서 글을 다시 선택해 주세요.",410)
            return {"channel":self.channel,"draft_id":item["draft"]["id"],"writer_url":item.get("writer_url"),"photo_count":len(item["draft"]["images"]),"expires_in":max(0,int(item["expires"]-time.time()))}
    def block(self,code):
        with self.lock:
            self.prune()
            if code not in self.tickets:
                raise HandoffError("전달 코드가 만료되었거나 사용됐어요.",410)
            del self.tickets[code]
            self.guard.block("크롬 확장에서 보호조치·추가 인증 화면을 확인했습니다.")
            return {"blocked":True}
    def redeem(self,code):
        with self.lock:
            self.prune()
            item=self.tickets.get(code)
            if not item:
                raise HandoffError("전달 코드가 만료되었거나 이미 사용됐어요. 앱에서 새 코드를 만들어 주세요.",410)
            draft=item["draft"]
            try:
                photos=[{"name":f"photo-{i+1}.jpg","base64":base64.b64encode((self.media/(mid+".jpg")).read_bytes()).decode()} for i,mid in enumerate(draft["images"])]
            except OSError:raise HandoffError("사진을 읽지 못해 입력을 시작하지 않았어요. 사진 파일을 확인한 뒤 같은 코드로 다시 시도해 주세요.",409)
            try:
                self.guard.reserve(draft["id"],allow_repeat=item.get("allow_repeat",False))
            except ValueError as error:
                raise HandoffError(str(error),409)
            del self.tickets[code]
            token=secrets.token_urlsafe(32)
            expected=len(draft["images"])
            from story_library import fingerprint
            self.reports[token]={"id":draft["id"],"photos":expected,"expires":time.time()+600,"fingerprint":fingerprint(draft,self.channel)}
            return {"title":draft["title"],"body":clean_blog(draft["blog"]),
                "photos":photos,
                "report_token":token,"expected_photos":expected,"format":template_for(draft.get("template"))}
    def report(self,token,state,count,diagnostic=None):
        with self.lock:
            self.prune()
            receipt=self.receipts.get(token)
            if receipt:
                if receipt["state"]!=state or type(receipt["count"]) is not type(count) or receipt["count"]!=count:raise HandoffError("이미 기록한 결과와 다른 요청이라 변경하지 않았어요.",409)
                return {"recorded":True,"state":state,"already_recorded":True}
            item=self.reports.get(token)
            if not item:
                raise HandoffError("보고 코드가 만료되었어요. 열린 편집기에서 결과를 확인해 주세요.",410)
            if state not in ("ready","partial","failed","blocked"):
                raise HandoffError("입력 결과 형식이 올바르지 않아요.")
            if state in ("ready","partial") and (type(count) is not int or count!=item["photos"]):
                raise HandoffError("선택한 사진 수와 입력 결과가 달라요. 완료로 기록하지 않았어요.",409)
            if isinstance(diagnostic,dict):
                safe={key:diagnostic[key] for key in ("version","state","stage","message","formatting","diagnostics") if key in diagnostic}
                encoded=json.dumps(safe,ensure_ascii=False,indent=2)
                if len(encoded.encode("utf-8"))<=100000:
                    destination=self.guard.path.parent/(self.channel+"-extension-diagnostics.json")
                    try:
                        temporary=destination.with_suffix(".tmp")
                        temporary.write_text(encoded,encoding="utf-8");temporary.replace(destination)
                    except OSError:pass
            if state in ("ready","partial"):
                self.guard.complete(item["id"])
            if state=="blocked":
                self.guard.block("크롬 확장에서 네이버 보호조치·추가 인증을 감지했습니다.")
            if self.record_report:self.record_report(token,item,state,count)
            del self.reports[token]
            self.receipts[token]={"state":state,"count":count,"expires":time.time()+600}
            while len(self.receipts)>64:self.receipts.pop(next(iter(self.receipts)))
            return {"recorded":True,"state":state}
