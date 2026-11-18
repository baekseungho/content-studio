"""네이버 자동 입력 재실행 제한. 보호조치를 우회하거나 자동 해제하지 않는다."""
import json
import math
from pathlib import Path
import threading
import time

class NaverGuard:
    def __init__(self,path):
        self.path=Path(path)
        self.lock=threading.RLock()
    def read(self):
        if not self.path.exists():
            return {"attempts":[],"completed":[],"blocked":False}
        try:
            state=json.loads(self.path.read_text(encoding="utf-8"))
            if not isinstance(state,dict):raise ValueError("invalid guard state")
            attempts=state.get("attempts",[]);completed=state.get("completed",[])
            if not isinstance(attempts,list) or any(type(value) not in (int,float) or not math.isfinite(value) for value in attempts):raise ValueError("invalid attempt history")
            if not isinstance(completed,list) or any(not isinstance(value,str) for value in completed):raise ValueError("invalid completion history")
            if type(state.get("blocked",False)) is not bool or not isinstance(state.get("reason",""),str):raise ValueError("invalid block state")
            return state
        except (ValueError,OSError):
            # 손상된 상태를 무시해 반복 실행하지 않는다.
            return {"attempts":[],"completed":[],"blocked":True,"reason":"이전 실행 상태를 확인할 수 없어요."}
    def write(self,state):
        self.path.parent.mkdir(parents=True,exist_ok=True)
        temp=self.path.with_suffix(".tmp")
        temp.write_text(json.dumps(state,ensure_ascii=False),encoding="utf-8")
        temp.replace(self.path)
    def status(self):
        with self.lock:
            state=self.read()
            now=time.time()
            attempts=[t for t in state.get("attempts",[]) if now-t<86400]
            remaining=max(0,math.ceil(60-(now-max(attempts)))) if attempts else 0
            return {"blocked":bool(state.get("blocked")),"reason":state.get("reason",""),
                    "cooldown_seconds":remaining,"attempts_24h":len(attempts),"limit_24h":None}
    def reserve(self,did,allow_repeat=False):
        with self.lock:
            state=self.read()
            status=self.status()
            if status["blocked"]:
                raise ValueError("네이버 보호조치로 자동 입력을 잠갔어요. 공식 화면에서 직접 제한 해제와 정상 로그인을 확인한 후 잠금을 해제해 주세요.")
            if did in state.get("completed",[]) and not allow_repeat:
                raise ValueError("이 초안은 이전에 편집기에 입력됐어요. 다시 시험하려면 앱에서 ‘같은 글 다시 넣기’를 선택하고 빈 글쓰기 화면을 사용해 주세요.")
            if status["cooldown_seconds"]:
                raise ValueError(f"이전 입력 후 1분이 지나야 해요. {status['cooldown_seconds']}초 뒤 다시 시도해 주세요.")
            state["attempts"]=[t for t in state.get("attempts",[]) if time.time()-t<86400]+[time.time()]
            self.write(state)
    def complete(self,did):
        with self.lock:
            state=self.read()
            state["completed"]=list(dict.fromkeys(state.get("completed",[])+[did]))
            self.write(state)
    def block(self,reason):
        with self.lock:
            state=self.read()
            state.update(blocked=True,reason=reason)
            self.write(state)
    def unblock(self):
        with self.lock:
            state=self.read()
            state.update(blocked=False,reason="")
            # 쿨다운과 시도 기록은 초기화하지 않는다. 일일 상한은 없다.
            self.write(state)
