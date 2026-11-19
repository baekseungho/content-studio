"""임시 사진 전용 Cloudflare 연결. HTML/API/원본 사진은 제공하지 않는다."""
import atexit
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import queue
import re
import subprocess
import threading
import time
from urllib.parse import urlparse
import urllib.request

class MediaTunnel:
    def __init__(self,root,media):
        self.root=Path(root)
        self.media=Path(media)
        self.lock=threading.RLock()
        self.allowed=set()
        self.process=None
        self.server=None
        self.thread=None
        self.url=""
        atexit.register(self.close)

    def active(self):
        return bool(self.url and self.process is not None and self.process.poll() is None)

    def allow(self,mid):
        if re.fullmatch(r"[a-f0-9]{32}",mid):
            with self.lock:
                self.allowed.add(mid)

    def allow_variant(self,name):
        from channel_media import VARIANT
        if isinstance(name,str) and VARIANT.fullmatch(name) and (self.media/name).is_file():
            with self.lock:self.allowed.add(name)

    def handler(self):
        owner=self
        class Gateway(BaseHTTPRequestHandler):
            def log_message(self,*args):
                pass
            def deliver(self,head=False):
                path=urlparse(self.path).path
                content=None
                mime="text/plain"
                status=404
                if path=="/health":
                    content=b"media-gateway-ready";status=200
                else:
                    match=re.fullmatch(r"/media/([a-f0-9]{32})(-ig|-(?:ig|th)-[a-f0-9]{16})\.jpg",path)
                    if match:
                        with owner.lock:
                            name=match[1]+match[2]+".jpg"
                            allowed=(match[1] in owner.allowed if match[2]=="-ig" else name in owner.allowed)
                        target=owner.media/name
                        if allowed and target.is_file():
                            content=target.read_bytes();mime="image/jpeg";status=200
                content=content if content is not None else b"Not found"
                self.send_response(status)
                self.send_header("Content-Type",mime)
                self.send_header("Content-Length",str(len(content)))
                self.send_header("Cache-Control","no-store")
                self.send_header("X-Content-Type-Options","nosniff")
                self.end_headers()
                if not head:
                    self.wfile.write(content)
            def do_GET(self):
                self.deliver()
            def do_HEAD(self):
                self.deliver(head=True)
        return Gateway

    def start(self,progress=lambda message:None):
        with self.lock:
            if self.active():
                return self.url
            self._close()
            binary=self.root/"tools"/"cloudflared.exe"
            if not binary.is_file():
                raise RuntimeError("사진 연결 도구가 없어요. tools/cloudflared.exe 설치가 필요해요.")
            self.server=ThreadingHTTPServer(("127.0.0.1",0),self.handler())
            self.thread=threading.Thread(target=self.server.serve_forever,daemon=True)
            self.thread.start()
            origin="http://127.0.0.1:"+str(self.server.server_address[1])
            config=self.media.parent/"tunnel-config.yml"
            config.write_text("loglevel: info\n",encoding="utf-8")
            self.process=subprocess.Popen([str(binary),"tunnel","--config",str(config),
                "--url",origin,"--protocol","http2","--no-autoupdate"],stdout=subprocess.DEVNULL,
                stderr=subprocess.PIPE,text=True,encoding="utf-8",errors="replace",
                creationflags=getattr(subprocess,"CREATE_NO_WINDOW",0))
            output=queue.Queue()
            def read():
                for line in self.process.stderr:
                    output.put(line)
            threading.Thread(target=read,daemon=True).start()
            progress("사진 전용 임시 HTTPS 주소를 만들고 있어요.")
            deadline=time.monotonic()+80
            candidate=""
            registered=False
            try:
                while time.monotonic()<deadline:
                    if self.process.poll() is not None:
                        raise RuntimeError("사진 연결 도구가 종료됐어요. 네트워크 연결을 확인해 주세요.")
                    try:
                        line=output.get(timeout=.5)
                    except queue.Empty:
                        continue
                    match=re.search(r"https://[a-z0-9-]+\.trycloudflare\.com",line)
                    if match:
                        candidate=match[0]
                        progress("사진 주소 연결을 확인하고 있어요.")
                    if "Registered tunnel connection" in line:
                        registered=True
                    if candidate and registered:
                        last_error="unknown"
                        for _ in range(12):
                            try:
                                with urllib.request.urlopen(candidate+"/health",timeout=8) as response:
                                    if response.read()==b"media-gateway-ready":
                                        self.url=candidate
                                        return self.url
                            except Exception as error:
                                last_error=str(getattr(error,"code",type(error).__name__))
                                time.sleep(2)
                        raise RuntimeError("사진 주소의 외부 연결을 확인하지 못했어요 ("+last_error+"). 잠시 후 다시 연결해 주세요.")
                raise RuntimeError("사진 주소 연결 시간이 초과됐어요. 네트워크 연결을 확인해 주세요.")
            except Exception:
                self._close()
                raise

    def _close(self):
        self.url=""
        self.allowed.clear()
        if self.process is not None:
            if self.process.poll() is None:
                self.process.terminate()
                try:
                    self.process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    self.process.kill()
                    self.process.wait(timeout=5)
            if self.process.stderr:
                self.process.stderr.close()
            self.process=None
        if self.server is not None:
            self.server.shutdown()
            self.server.server_close()
            self.server=None
            self.thread=None

    def close(self):
        with self.lock:
            self._close()
