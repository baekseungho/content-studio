"""Read-only Instagram token check. Never prints credentials or account identity."""
import json
import os
from pathlib import Path
import sys
import urllib.error
import urllib.request
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import app
token=os.environ.get("INSTAGRAM_ACCESS_TOKEN","")
if not token:
    print(json.dumps({"token_configured":False}))
else:
    version=os.environ.get("INSTAGRAM_API_VERSION","v27.0")
    req=urllib.request.Request("https://graph.instagram.com/"+version+"/me?fields=id",
        headers={"Authorization":"Bearer "+token})
    try:
        with urllib.request.urlopen(req,timeout=20) as response:
            body=json.load(response)
        print(json.dumps({"authenticated":True,"configured_account_id_matches":str(body.get("id",""))==os.environ.get("INSTAGRAM_ACCOUNT_ID","")}))
    except urllib.error.HTTPError as error:
        try:
            payload=json.loads(error.read()).get("error",{})
        except Exception:
            payload={}
        print(json.dumps({"authenticated":False,"http_status":error.code,"error_type":payload.get("type"),
                          "error_code":payload.get("code"),"error_subcode":payload.get("error_subcode")}))
        error.close()
    except Exception as error:
        print(json.dumps({"authenticated":False,"connection_error_type":type(error).__name__}))
