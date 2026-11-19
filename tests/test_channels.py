"""Channel photo independence, exact previews, publishing parity and scoped adaptation."""
import base64,concurrent.futures,copy,hashlib,io,json,os,tempfile,threading,unittest,urllib.error,urllib.request
from pathlib import Path
from unittest.mock import patch
from PIL import Image
import app
from channel_media import config,read,view,selected,prepare,preview
from channel_adaptation import prepare as adaptation,validate as validate_adaptation,generate as adapt
from media_tunnel import MediaTunnel,ThreadingHTTPServer

class ChannelMediaTests(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name);self.mid="a"*32
  image=Image.new("RGB",(600,300),"red");image.paste("blue",(300,0,600,300));image.save(self.root/(self.mid+".jpg"),quality=95);self.original=(self.root/(self.mid+".jpg")).read_bytes()
 def tearDown(self):self.temp.cleanup()
 def settings(self,frame="square",mode="cover",x=50):return {"version":1,"images":[self.mid],"frame":frame,"adjustments":{self.mid:{"mode":mode,"x":x,"y":50}}}
 def test_invalid_config_and_duplicates_rejected(self):
  for value in ({"images":[self.mid,self.mid]},{"images":["../bad"]},{"images":[self.mid],"frame":"original"},{"images":[self.mid],"adjustments":{self.mid:{"x":float("nan")}}},{"images":[],"adjustments":{self.mid:{}}}):
   with self.subTest(value=value),self.assertRaises(ValueError):config(value,"instagram")
 def test_explicit_empty_is_not_legacy_fallback(self):
  draft={"images":[self.mid],"channel_media":{"instagram":{"images":[]},"threads":{"images":[self.mid]}}}
  self.assertEqual(selected(draft,"instagram"),[]);self.assertEqual(selected(draft,"threads"),[self.mid]);self.assertEqual(view({**draft,"threads_include_images":False},"threads")["images"],[])
 def test_legacy_and_other_channel_unchanged(self):
  self.assertEqual(view({"images":[self.mid]},"instagram")["images"],[self.mid]);self.assertEqual(view({"images":[self.mid]},"naver"),{"images":[self.mid]})
 def test_preview_matches_published_jpeg_and_creates_no_file(self):
  result=preview(self.root,self.mid,self.settings(),"instagram");self.assertEqual(len(list(self.root.iterdir())),1)
  ready=prepare(self.root,self.mid,self.settings(),"instagram");self.assertEqual(base64.b64decode(result["src"].split(",",1)[1]),ready.read_bytes());self.assertEqual((result["width"],result["height"]),(1080,1080));self.assertEqual((self.root/(self.mid+".jpg")).read_bytes(),self.original)
 def test_crop_positions_and_contain_have_expected_pixels(self):
  left=prepare(self.root,self.mid,self.settings(x=0),"instagram");right=prepare(self.root,self.mid,self.settings(x=100),"instagram");self.assertNotEqual(left,right)
  with Image.open(left) as image:self.assertGreater(image.getpixel((100,500))[0],230)
  with Image.open(right) as image:self.assertGreater(image.getpixel((900,500))[2],230)
  padded=prepare(self.root,self.mid,self.settings(mode="contain"),"instagram")
  with Image.open(padded) as image:self.assertGreater(min(image.getpixel((500,20))),230)
 def test_all_instagram_frames_supported(self):
  for frame,size in (("portrait",(1080,1350)),("square",(1080,1080)),("landscape",(1080,566))):
   with Image.open(prepare(self.root,self.mid,self.settings(frame=frame),"instagram")) as image:self.assertEqual(image.size,size)
 def test_threads_original_and_channel_names_do_not_collide(self):
  ig=prepare(self.root,self.mid,self.settings(),"instagram");original=ig.read_bytes();th=prepare(self.root,self.mid,{"images":[self.mid],"frame":"original"},"threads")
  self.assertNotEqual(ig,th);self.assertIn("-th-",th.name);self.assertEqual(ig.read_bytes(),original)
  with Image.open(th) as image:self.assertEqual(image.size,(600,300))
 def test_concurrent_derivatives_are_complete_and_reusable(self):
  with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:paths=list(pool.map(lambda _:prepare(self.root,self.mid,self.settings(),"instagram"),range(8)))
  self.assertEqual(len(set(paths)),1)
  with Image.open(paths[0]) as image:image.load();self.assertEqual(image.size,(1080,1080))
  self.assertFalse(list(self.root.glob("*.tmp")))
 def test_gateway_allows_only_exact_ready_variant(self):
  first=prepare(self.root,self.mid,self.settings(x=0),"instagram");second=prepare(self.root,self.mid,self.settings(x=100),"instagram");gateway=MediaTunnel(self.root,self.root);server=ThreadingHTTPServer(("127.0.0.1",0),gateway.handler());thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start();base="http://127.0.0.1:"+str(server.server_port)
  try:
   gateway.allow(self.mid)
   with self.assertRaises(urllib.error.HTTPError):urllib.request.urlopen(base+"/media/"+first.name)
   gateway.allow_variant(first.name)
   with urllib.request.urlopen(base+"/media/"+first.name) as result:self.assertEqual(result.read(),first.read_bytes())
   with self.assertRaises(urllib.error.HTTPError):urllib.request.urlopen(base+"/media/"+second.name)
   with self.assertRaises(urllib.error.HTTPError):urllib.request.urlopen(base+"/media/"+self.mid+".jpg")
  finally:server.shutdown();server.server_close();thread.join();gateway.close()

class ChannelPublishingTests(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name);self.media=self.root/"media";self.media.mkdir();self.ids=[str(i)*32 for i in (1,2,3)]
  for mid in self.ids:Image.new("RGB",(600,400),"red").save(self.media/(mid+".jpg"))
  self.patches=[patch.object(app,"DATA",self.root),patch.object(app,"MEDIA",self.media),patch.object(app,"media_base_url",return_value="https://photos.example.com"),patch.dict(os.environ,{"THREADS_USER_ID":"777","THREADS_ACCESS_TOKEN":"mock","INSTAGRAM_ACCOUNT_ID":"888"})]
  for item in self.patches:item.start()
  with app.db() as db:db.executescript("CREATE TABLE drafts(id TEXT PRIMARY KEY,title TEXT,data TEXT,updated REAL);CREATE TABLE attempts(id TEXT PRIMARY KEY,draft_id TEXT,state TEXT,result TEXT,created REAL);")
  self.calls=[]
 def tearDown(self):
  for item in reversed(self.patches):item.stop()
  self.temp.cleanup()
 def draft(self,**extra):return app.save_draft({"title":"블로그 제목","blog":"블로그 본문","instagram":"인스타 이야기","threads":"스레드 이야기","images":self.ids,"channel_media":{"instagram":{"images":[self.ids[1]],"frame":"square"},"threads":{"images":[self.ids[2],self.ids[0]],"frame":"original"}},**extra})
 def test_save_view_and_root_photos_stay_independent(self):
  saved=self.draft();self.assertEqual(saved["images"],self.ids);self.assertEqual(app.platform_view(saved,"instagram")["images"],[self.ids[1]]);self.assertEqual(app.platform_view(saved,"threads")["images"],[self.ids[2],self.ids[0]])
 def test_instagram_posts_selected_order_and_rendered_file(self):
  saved=self.draft()
  def graph(path,payload):self.calls.append((path,payload));return {"id":"container" if not path.endswith("media_publish") else "published"}
  with patch.object(app,"instagram_configuration",return_value={"ready":True}),patch.object(app,"graph",side_effect=graph),patch.object(app,"wait_container"):app.publish_instagram(saved["id"])
  images=[payload["image_url"] for path,payload in self.calls if "image_url" in payload];self.assertEqual(len(images),1);self.assertIn(self.ids[1]+"-ig-",images[0]);self.assertEqual(app.get_draft(saved["id"])["images"],self.ids)
  with Image.open(self.media/images[0].rsplit("/",1)[-1]) as image:self.assertEqual(image.size,(1080,1080))
 def test_instagram_missing_selected_file_fails_before_attempt(self):
  saved=self.draft();(self.media/(self.ids[1]+".jpg")).unlink()
  with patch.object(app,"instagram_configuration",return_value={"ready":True}),patch.object(app,"graph") as graph:
   with self.assertRaises(app.Problem):app.publish_instagram(saved["id"])
   graph.assert_not_called()
  with app.db() as db:self.assertEqual(db.execute("SELECT COUNT(*) FROM attempts").fetchone()[0],0)
 def test_threads_uses_own_order_and_original_ratio(self):
  saved=self.draft()
  def remote(url,payload=None,*args,**kwargs):
   self.calls.append((url,payload))
   if "/me?" in url:return {"id":"777","username":"mock"}
   if "?fields=status" in url:return {"status":"FINISHED"}
   return {"id":"item"+str(len(self.calls))}
  with patch.object(app,"remote",side_effect=remote):app.threads_service().publish(saved["id"])
  images=[body["image_url"] for _,body in self.calls if body and "image_url" in body];self.assertEqual(len(images),2);self.assertIn(self.ids[2]+"-th-",images[0]);self.assertIn(self.ids[0]+"-th-",images[1])
 def test_text_only_threads_ignores_selected_photos(self):
  saved=self.draft(threads_include_images=False)
  def remote(url,payload=None,*args,**kwargs):
   self.calls.append((url,payload))
   if "/me?" in url:return {"id":"777","username":"mock"}
   if "?fields=status" in url:return {"status":"FINISHED"}
   return {"id":"item"}
  with patch.object(app,"remote",side_effect=remote):app.threads_service().publish(saved["id"])
  self.assertFalse(any(body and "image_url" in body for _,body in self.calls))
 def test_generation_uses_only_each_channels_selected_photos(self):
  def remote(url,payload,key):
   context=json.loads(payload["input"][0]["content"][0]["text"]);self.calls.append((context,payload));return {"output":[{"type":"message","content":[{"type":"output_text","text":json.dumps({p:"확인한 이야기" for p in context["requested_platforms"]})}]}]}
  with patch.dict(os.environ,{"OPENAI_API_KEY":"mock"}),patch.object(app,"remote",side_effect=remote):result=app.generate({"platforms":["instagram","threads"],"prompt":"확인한 카페 이야기","tone":"담백하고 차분하게","images":self.ids,"channel_images":{"instagram":[self.ids[1]],"threads":[]}})
  self.assertEqual(len(self.calls),2);self.assertEqual([c[0]["requested_platforms"] for c in self.calls],[["instagram"],["threads"]]);self.assertEqual([sum(part["type"]=="input_image" for part in c[1]["input"][0]["content"]) for c in self.calls],[1,0]);self.assertEqual(result["generated_platforms"],["instagram","threads"])
 def test_unselected_channel_photo_mapping_rejected(self):
  with patch.dict(os.environ,{"OPENAI_API_KEY":"mock"}),patch.object(app,"remote") as remote:
   with self.assertRaises(app.Problem):app.generate({"platforms":["threads"],"prompt":"카페","images":[],"channel_images":{"instagram":[]}})
  remote.assert_not_called()

class AdaptationTests(unittest.TestCase):
 def request(self,**extra):return {"platform":"instagram","source_checked":True,"source":{"platform":"naver","title":"카페 기록","body":"라떼 2잔을 마셨어요.\n\n[[photo:1]]\n\n크림이 고소했어요.\n\n#카페"},"language":"ko","facts":"","disclosure":"none",**extra}
 def test_source_is_explicit_and_has_no_photo_tokens(self):
  req=adaptation(self.request());self.assertNotIn("[[photo",req["source"]["body"]);self.assertNotIn("#카페",req["source"]["body"])
  with self.assertRaises(ValueError):adaptation(self.request(source_checked=False))
 def test_new_numbers_are_rejected_but_shortening_is_allowed(self):
  req=adaptation(self.request());self.assertFalse(validate_adaptation(req,"라떼 3잔을 마셨어요.")["can_apply"]);self.assertTrue(validate_adaptation(req,"고소한 크림이 기억에 남아요.")["can_apply"])
 def test_sponsorship_and_instagram_facts_are_protected(self):
  req=adaptation(self.request(disclosure="gifted",facts="토요일에 다녀왔어요."));self.assertFalse(validate_adaptation(req,"크림이 고소했어요.")["can_apply"]);self.assertTrue(validate_adaptation(req,"제품을 제공받아 작성한 글입니다.\n\n토요일에 다녀왔어요.")["can_apply"])
 def test_english_mixing_and_overlong_threads_rejected(self):
  req=adaptation(self.request(language="en"));self.assertFalse(validate_adaptation(req,"A latte 크림.")["can_apply"])
  req=adaptation(self.request(platform="threads"))
  result=validate_adaptation(req,"a"*501);self.assertFalse(result["can_apply"]);self.assertEqual(len(result["text"]),501)
 def test_one_text_call_no_history_other_draft_or_search(self):
  req=adaptation(self.request(other_draft="PRIVATE OTHER DRAFT",voice={"sample":"PRIVATE STYLE EXAMPLE"}));calls=[]
  def remote(url,payload,key):calls.append(payload);return {"output":[{"type":"message","content":[{"type":"output_text","text":json.dumps({"instagram":"크림이 고소하더라고요."})}]}]}
  from types import SimpleNamespace
  with patch.dict(os.environ,{"OPENAI_API_KEY":"mock"}):result=adapt(req,SimpleNamespace(remote=remote,Problem=app.Problem),lambda *a:None)
  self.assertTrue(result["can_apply"],result);self.assertEqual(len(calls),1);self.assertNotIn("PRIVATE OTHER",str(calls));self.assertNotIn("input_image",str(calls));self.assertNotIn("tools",calls[0]);self.assertFalse(calls[0]["store"])
 def test_translated_numbers_and_units_preserve_the_same_quantity(self):
  req=adaptation(self.request(language="en"));self.assertTrue(validate_adaptation(req,"I had 2 cups.")["can_apply"])
  self.assertFalse(validate_adaptation(req,"I stayed 2 days.")["can_apply"]);self.assertFalse(validate_adaptation(req,"I had 3 cups.")["can_apply"])
  req=adaptation(self.request(language="en",source={"platform":"naver","body":"가격은 2만원이에요."}));self.assertTrue(validate_adaptation(req,"It was 20,000 won.")["can_apply"]);self.assertFalse(validate_adaptation(req,"It was $20,000.")["can_apply"])
 def test_overlong_model_proposal_is_retained_for_free_repair(self):
  from types import SimpleNamespace
  req=adaptation(self.request(platform="threads"));response={"output":[{"type":"message","content":[{"type":"output_text","text":json.dumps({"threads":"a"*510})}]}]}
  with patch.dict(os.environ,{"OPENAI_API_KEY":"mock"}):result=adapt(req,SimpleNamespace(remote=lambda *a:response,Problem=app.Problem),lambda *a:None)
  self.assertFalse(result["can_apply"]);self.assertEqual(result["text"],"a"*510);self.assertTrue(validate_adaptation(req,"짧게 남긴 카페 이야기")["can_apply"])
 def test_empty_and_excessive_source_are_not_silently_truncated(self):
  for value in ("", "x"*12001):
   with self.subTest(value=value[:10]),self.assertRaises(ValueError):adaptation(self.request(source={"platform":"naver","body":value}))

if __name__=="__main__":unittest.main()
