import io
from pathlib import Path
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from PIL import Image
from media_tunnel import MediaTunnel, ThreadingHTTPServer

class GatewayTests(unittest.TestCase):
    def test_only_allowed_derivatives_are_public(self):
        with tempfile.TemporaryDirectory(prefix="media-gateway-test-") as temp:
            root=Path(temp)
            gateway=MediaTunnel(root,root)
            mid="a"*32
            buffer=io.BytesIO()
            Image.new("RGB",(4,4),"green").save(buffer,"JPEG")
            (root/(mid+"-ig.jpg")).write_bytes(buffer.getvalue())
            (root/(mid+".jpg")).write_bytes(buffer.getvalue())
            (root/".env").write_text("SECRET",encoding="utf-8")
            server=ThreadingHTTPServer(("127.0.0.1",0),gateway.handler())
            thread=threading.Thread(target=server.serve_forever,daemon=True)
            thread.start()
            base="http://127.0.0.1:"+str(server.server_address[1])
            try:
                for path in ("/","/api/status","/.env","/data/studio.db","/media/"+mid+".jpg","/media/"+mid+"-ig.jpg"):
                    with self.assertRaises(urllib.error.HTTPError) as result:
                        urllib.request.urlopen(base+path)
                    self.assertEqual(result.exception.code,404)
                    result.exception.close()
                gateway.allow(mid)
                with urllib.request.urlopen(base+"/media/"+mid+"-ig.jpg") as result:
                    self.assertEqual(result.read(),buffer.getvalue())
                req=urllib.request.Request(base+"/media/"+mid+"-ig.jpg",method="HEAD")
                with urllib.request.urlopen(req) as result:
                    self.assertEqual(result.headers["Content-Type"],"image/jpeg")
                    self.assertEqual(result.read(),b"")
                with urllib.request.urlopen(base+"/health") as result:
                    self.assertEqual(result.read(),b"media-gateway-ready")
            finally:
                server.shutdown()
                server.server_close()
                thread.join()
                gateway.close()

if __name__=="__main__":
    unittest.main()
