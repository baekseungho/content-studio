"""HTTP boundaries: validation before jobs, one bounded model call and profile CAS."""
import json,os,tempfile,threading,time,unittest,urllib.error,urllib.request
from pathlib import Path
from unittest.mock import patch
from http.server import ThreadingHTTPServer
import app
from voice_profiles import VoiceStore

class WritingAPITests(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.voices=patch.object(app,"VOICES",VoiceStore(Path(self.temp.name)/"voices.json"));self.voices.start();self.env=patch.dict(os.environ,{"OPENAI_API_KEY":"test-only"});self.env.start()
  self.jobs=patch.object(app,"JOBS",{});self.jobs.start();self.server=ThreadingHTTPServer(("127.0.0.1",0),app.Handler);self.base="http://127.0.0.1:"+str(self.server.server_port);self.host=patch.object(app,"HOSTS",{self.base.removeprefix("http://")});self.host.start();self.thread=threading.Thread(target=self.server.serve_forever,daemon=True);self.thread.start()
 def tearDown(self):
  self.server.shutdown();self.server.server_close();self.thread.join();self.host.stop();self.jobs.stop();self.env.stop();self.voices.stop();self.temp.cleanup()
 def call(self,path,body=None,token=True):
  headers={"Content-Type":"application/json"}
  if token:headers["X-Studio-Token"]=app.TOKEN
  request=urllib.request.Request(self.base+path,data=json.dumps(body).encode() if body is not None else None,headers=headers)
  try:
   with urllib.request.urlopen(request,timeout=3) as response:return response.status,json.load(response)
  except urllib.error.HTTPError as error:return error.code,json.load(error)
 def request(self):return {"platform":"threads","body":"좋았어요.","target":{"kind":"body"},"notes":"카페가 좋았어요."}
 def test_no_auth_no_work(self):
  status,_=self.call("/api/writing/refine",self.request(),False);self.assertEqual(status,403);self.assertFalse(app.JOBS)
 def test_invalid_selection_allocates_no_job(self):
  status,_=self.call("/api/writing/refine",{**self.request(),"target":{"kind":"body","start":50}});self.assertEqual(status,400);self.assertFalse(app.JOBS)
 def test_missing_ai_key_allocates_no_job(self):
  with patch.dict(os.environ,{"OPENAI_API_KEY":""}):status,_=self.call("/api/writing/refine",self.request())
  self.assertEqual(status,409);self.assertFalse(app.JOBS)
 def test_free_candidate_validation_calls_no_model(self):
  with patch.object(app,"remote",side_effect=AssertionError("Unexpected remote call")):
   status,result=self.call("/api/writing/validate",{**self.request(),"candidate":"좋더라고요."})
  self.assertEqual(status,200);self.assertTrue(result["can_apply"]);self.assertFalse(app.JOBS)
 def test_real_job_with_mocked_remote_completes_once(self):
  response={"output":[{"type":"message","content":[{"type":"output_text","text":json.dumps({"text":"좋더라고요."})}]}]}
  with patch.object(app,"remote",return_value=response) as remote:
   status,job=self.call("/api/writing/refine",self.request());self.assertEqual(status,200)
   for _ in range(50):
    _,result=self.call("/api/jobs/"+job["job"])
    if result["state"]!="running":break
    time.sleep(.01)
   self.assertEqual(result["state"],"done",result);self.assertTrue(result["result"]["choices"][0]["can_apply"]);self.assertEqual(remote.call_count,1)
 def test_writing_job_exclusion(self):
  app.JOBS["existing"]={"state":"running","_kind":"writing"}
  status,data=self.call("/api/writing/refine",self.request());self.assertEqual(status,409);self.assertEqual(data["code"],"job_in_progress");self.assertEqual(len(app.JOBS),1)
 def test_voice_store_optimistic_conflict_preserves_value(self):
  status,data=self.call("/api/voice-profiles",{"channel":"threads","profile":{"preset":"witty"},"revision":0});self.assertEqual(status,200);self.assertEqual(data["revision"],1)
  status,data=self.call("/api/voice-profiles",{"channel":"threads","profile":{"preset":"calm"},"revision":0});self.assertEqual(status,409);self.assertEqual(data["code"],"voice_conflict");self.assertEqual(self.call("/api/voice-profiles")[1]["profiles"]["threads"]["preset"],"witty")
 def test_profile_analysis_does_not_create_job(self):
  status,data=self.call("/api/voice/analyze",{"sample":"창가에 앉았어요. 고소한 라떼를 마셨어요. 짧게 기록을 남겨요."});self.assertEqual(status,200);self.assertEqual(data["profile"]["formality"],"polite");self.assertFalse(app.JOBS)


 def test_channel_preview_stays_private_and_calls_no_ai(self):
  from PIL import Image
  root=Path(self.temp.name);mid="b"*32;Image.new("RGB",(400,200),"red").save(root/(mid+".jpg"))
  with patch.object(app,"MEDIA",root),patch.object(app,"remote",side_effect=AssertionError("Unexpected AI")):
   status,result=self.call("/api/channel-media/preview",{"channel":"instagram","image_id":mid,"settings":{"images":[mid],"frame":"square"}})
  self.assertEqual(status,200);self.assertTrue(result["src"].startswith("data:image/jpeg;base64,"));self.assertEqual(result["width"],1080);self.assertEqual(len(list(root.glob("*.jpg"))),1);self.assertFalse(app.JOBS)
 def test_channel_preview_requires_auth(self):
  status,_=self.call("/api/channel-media/preview",{"channel":"instagram"},False);self.assertEqual(status,403)
 def adaptation_request(self):return {"platform":"instagram","source_checked":True,"source":{"platform":"naver","body":"라떼 2잔을 마셨어요."},"language":"ko"}
 def test_adaptation_confirmation_precedes_job(self):
  status,_=self.call("/api/channel/adapt",{**self.adaptation_request(),"source_checked":False});self.assertEqual(status,400);self.assertFalse(app.JOBS)
 def test_adaptation_free_validation(self):
  with patch.object(app,"remote",side_effect=AssertionError("Unexpected AI")):
   status,result=self.call("/api/channel/adapt/validate",{**self.adaptation_request(),"candidate":"라떼 3잔을 마셨어요."})
  self.assertEqual(status,200);self.assertFalse(result["can_apply"]);self.assertFalse(app.JOBS)
 def test_adaptation_runs_one_text_job(self):
  response={"output":[{"type":"message","content":[{"type":"output_text","text":json.dumps({"instagram":"라떼 2잔을 마셨어요."})}]}]}
  with patch.object(app,"remote",return_value=response) as remote:
   status,job=self.call("/api/channel/adapt",self.adaptation_request());self.assertEqual(status,200)
   for _ in range(50):
    _,result=self.call("/api/jobs/"+job["job"])
    if result["state"]!="running":break
    time.sleep(.01)
   self.assertEqual(result["state"],"done");self.assertTrue(result["result"]["can_apply"]);self.assertEqual(remote.call_count,1)

if __name__=="__main__":unittest.main()
