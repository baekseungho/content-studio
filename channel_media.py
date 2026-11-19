"""Per-channel photo selections. Prepared originals and blog blocks stay independent."""
import hashlib,json,math,re
from pathlib import Path
from PIL import Image,ImageOps
from publish_media import _PHOTO_LOCKS
import os,tempfile

CHANNELS=("instagram","threads")
FRAMES={"portrait":(1080,1350),"square":(1080,1080),"landscape":(1080,566),"original":None}
ID=re.compile(r"[a-f0-9]{32}\Z")
VARIANT=re.compile(r"[a-f0-9]{32}-(?:ig|th)-[a-f0-9]{16}\.jpg\Z")


def ids(value):
 if not isinstance(value,list) or len(value)>10 or any(not isinstance(x,str) or not ID.fullmatch(x) for x in value) or len(set(value))!=len(value):raise ValueError("채널 사진은 중복 없이 10장까지 골라 주세요.")
 return list(value)


def adjustment(value):
 if not isinstance(value,dict):raise ValueError("사진 맞춤 설정을 다시 골라 주세요.")
 mode=value.get("mode","contain")
 if mode not in ("contain","cover"):raise ValueError("사진 맞춤 방법을 다시 골라 주세요.")
 result={"mode":mode}
 for key in ("x","y"):
  number=value.get(key,50)
  if type(number) not in (int,float) or not math.isfinite(number) or not 0<=number<=100:raise ValueError("사진 위치는 0~100 사이로 맞춰 주세요.")
  result[key]=round(number,2)
 return result


def config(value,channel):
 if channel not in CHANNELS or not isinstance(value,dict) or type(value.get("version",1)) is not int or value.get("version",1)!=1:raise ValueError("사진 설정을 다시 불러와 주세요.")
 photos=ids(value.get("images",[]));frame=value.get("frame","original" if channel=="threads" else "portrait")
 if not isinstance(frame,str) or frame not in FRAMES or (channel=="instagram" and frame=="original"):raise ValueError("이 채널에서 쓸 사진 비율을 다시 골라 주세요.")
 raw=value.get("adjustments",{})
 if not isinstance(raw,dict) or len(raw)>10 or any(key not in photos for key in raw):raise ValueError("현재 선택한 사진의 맞춤 설정만 저장할 수 있어요.")
 return {"version":1,"images":photos,"frame":frame,"adjustments":{key:adjustment(item) for key,item in raw.items()}}


def read(value):
 if value is None:return {}
 if not isinstance(value,dict) or any(key not in CHANNELS for key in value):raise ValueError("채널별 사진 선택을 확인해 주세요.")
 return {key:config(item,key) for key,item in value.items()}


def selected(draft,channel):
 settings=read(draft.get("channel_media"))
 return settings[channel]["images"] if channel in settings else list(draft.get("images",[]))


def view(draft,channel):
 result=dict(draft)
 if channel in CHANNELS:
  result["images"]=selected(draft,channel)
  if channel=="threads" and draft.get("threads_include_images") is False:result["images"]=[]
 return result


def options(settings,channel,mid):
 clean=config(settings,channel)
 if mid not in clean["images"]:raise ValueError("이 채널에서 선택한 사진이 아니에요.")
 return {"channel":channel,"frame":clean["frame"],**clean["adjustments"].get(mid,adjustment({})),"renderer":1}


def filename(mid,option):
 if not isinstance(mid,str) or not ID.fullmatch(mid):raise ValueError("사진 번호를 확인해 주세요.")
 digest=hashlib.sha256(json.dumps(option,sort_keys=True,separators=(",",":")).encode()).hexdigest()[:16]
 return mid+("-ig-" if option["channel"]=="instagram" else "-th-")+digest+".jpg"


def render(media,mid,settings,channel):
 option=options(settings,channel,mid)
 with Image.open(Path(media)/(mid+".jpg")) as source:
  image=ImageOps.exif_transpose(source).convert("RGB")
  size=FRAMES[option["frame"]]
  if size is None:
   ratio=min(10,max(.1,image.width/image.height));width=max(320,min(1080,image.width));size=(width,max(1,round(width/ratio)))
  center=(option["x"]/100,option["y"]/100)
  output=ImageOps.fit(image,size,method=Image.Resampling.LANCZOS,centering=center) if option["mode"]=="cover" and option["frame"]!="original" else ImageOps.pad(image,size,method=Image.Resampling.LANCZOS,color="#faf8f5",centering=(.5,.5))
  return output


def preview(media,mid,settings,channel):
 import io,base64
 with render(media,mid,settings,channel) as output:
  buffer=io.BytesIO();output.save(buffer,"JPEG",quality=90)
  return {"src":"data:image/jpeg;base64,"+base64.b64encode(buffer.getvalue()).decode(),"width":output.width,"height":output.height}


def prepare(media,mid,settings,channel):
 media=Path(media);option=options(settings,channel,mid);target=media/filename(mid,option)
 with _PHOTO_LOCKS[hash((str(media.resolve()),target.name))%len(_PHOTO_LOCKS)]:
  if target.is_file():return target
  fd,name=tempfile.mkstemp(prefix=mid+"-",suffix=".tmp",dir=media);os.close(fd);temporary=Path(name)
  try:
   with render(media,mid,settings,channel) as output:output.save(temporary,"JPEG",quality=90)
   os.replace(temporary,target)
  finally:temporary.unlink(missing_ok=True)
 return target
