"""Verify real external tunnel without publishing or serving personal photos."""
from pathlib import Path
import sys
import tempfile
import urllib.error
import urllib.request
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from media_tunnel import MediaTunnel
root=Path(__file__).resolve().parents[1]
with tempfile.TemporaryDirectory(prefix="tunnel-connectivity-") as temp:
    gateway=MediaTunnel(root,Path(temp)/"media")
    gateway.media.mkdir()
    try:
        url=gateway.start(lambda message:None)
        with urllib.request.urlopen(url+"/health",timeout=15) as response:
            assert response.read()==b"media-gateway-ready"
        for path in ("/","/api/status","/.env","/media/"+"a"*32+"-ig.jpg"):
            try:
                urllib.request.urlopen(url+path,timeout=15)
            except urllib.error.HTTPError as error:
                assert error.code==404,(path,error.code)
                error.close()
            else:
                raise AssertionError("Private route exposed: "+path)
        print("External HTTPS tunnel verified; app/API/private files unavailable; no photos shared.")
    finally:
        gateway.close()
