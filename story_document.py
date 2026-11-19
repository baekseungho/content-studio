"""Versioned blog blocks, stable photo references and legacy handoff serialization."""
import copy
import re
import uuid

FIELDS={"naver":("blog","title"),"tistory":("tistory","tistory_title")}
ID=re.compile(r"[a-f0-9]{32}\Z")
MAX_BLOCKS=250
MAX_HISTORY=20

def uid():return uuid.uuid4().hex

def photo_ids(document):
    return [b["image_id"] for b in document["blocks"] if b["type"]=="photo"]

def serialize(document):
    parts=[];number=0
    for block in document["blocks"]:
        if block["type"]=="photo":
            number+=1;parts.append("[[photo:"+str(number)+"]]")
            if block.get("caption"):parts.append(block["caption"])
        else:
            value=block.get("text","")
            if value:parts.append(("## " if block["type"]=="heading" else "")+value)
    return "\n\n".join(parts)

def parse(body,images,previous=None):
    blocks=[];used=set()
    # Split inline legacy photo anchors without dropping surrounding prose.
    chunks=re.split(r"(\[\[photo:\d+\]\])",body.replace("\r\n","\n"))
    for chunk in chunks:
        match=re.fullmatch(r"\[\[photo:(\d+)\]\]",chunk)
        if match:
            at=int(match[1])-1
            if 0<=at<len(images) and images[at] not in used:
                used.add(images[at]);blocks.append({"id":uid(),"type":"photo","image_id":images[at],"caption":""})
            continue
        for paragraph in re.split(r"\n[ \t]*\n",chunk):
            paragraph=paragraph.strip("\n")
            if not paragraph:continue
            # A heading line is a separate block even without surrounding blank lines.
            lines=[]
            def flush():
                if lines:blocks.append({"id":uid(),"type":"paragraph","text":"\n".join(lines)});lines.clear()
            for line in paragraph.split("\n"):
                if line.startswith("## "):flush();blocks.append({"id":uid(),"type":"heading","text":line[3:]})
                else:lines.append(line)
            flush()
    if previous:
        available=list(previous["blocks"])
        for block in blocks:
            old=next((b for b in available if b["type"]==block["type"] and (b.get("image_id")==block.get("image_id") if block["type"]=="photo" else b.get("text")==block.get("text"))),None)
            if old:
                block["id"]=old["id"];available.remove(old)
                if block["type"]=="photo" and old.get("caption"):
                    i=blocks.index(block)
                    if i+1<len(blocks) and re.sub(r"\s+","",blocks[i+1].get("text",""))==re.sub(r"\s+","",old["caption"]):
                        block["caption"]=blocks[i+1]["text"];blocks.pop(i+1)
    return blocks

def _text(value,maximum):
    if not isinstance(value,str) or len(value)>maximum:raise ValueError("블록의 글이 너무 길거나 형식이 맞지 않아요.")
    return value

def _blocks(value):
    if not isinstance(value,list) or len(value)>MAX_BLOCKS:raise ValueError("문단 수가 너무 많아요. 글을 나눠 주세요.")
    result=[];ids=set();photos=set()
    for block in value:
        if not isinstance(block,dict) or not isinstance(block.get("id"),str) or not ID.fullmatch(block["id"]) or block["id"] in ids:raise ValueError("문단 정보를 다시 불러와 주세요.")
        ids.add(block["id"]);kind=block.get("type");clean={"id":block["id"],"type":kind}
        if kind=="photo":
            image=block.get("image_id")
            if not isinstance(image,str) or not ID.fullmatch(image) or image in photos or len(photos)>=10:raise ValueError("사진은 한 원고에 중복 없이 최대 10장까지 넣을 수 있어요.")
            photos.add(image);clean.update(image_id=image,caption=_text(block.get("caption",""),2000))
        elif kind in ("paragraph","heading"):clean["text"]=_text(block.get("text",""),30000)
        else:raise ValueError("지원하지 않는 문단 형식이에요.")
        if any(re.search(r"\[\[photo:\d+\]\]",clean.get(k,"")) for k in ("text","caption")):raise ValueError("사진은 문단 코드 대신 사진 추가로 넣어 주세요.")
        result.append(clean)
    if len(serialize({"blocks":result}))>30000:raise ValueError("블로그 원고가 너무 길어요.")
    return result

def read_documents(value):
    if value is None:return {}
    if not isinstance(value,dict) or any(p not in FIELDS for p in value):raise ValueError("블로그 원고 정보를 확인해 주세요.")
    output={}
    for platform,doc in value.items():
        if not isinstance(doc,dict) or type(doc.get("version")) is not int or doc["version"]!=1:raise ValueError("이 원고는 앱을 업데이트한 뒤 열어 주세요.")
        clean={"version":1,"blocks":_blocks(doc.get("blocks")),"source":_text(doc.get("source",""),30000),"template":doc.get("template","reference")}
        if clean["template"] not in ("reference","clean"):raise ValueError("글 꾸미기 설정을 확인해 주세요.")
        original=doc.get("original",{})
        if not isinstance(original,dict):raise ValueError("원본 보관 정보를 확인해 주세요.")
        images=original.get("images",[])
        if not isinstance(images,list) or len(images)>10 or any(not isinstance(x,str) or not ID.fullmatch(x) for x in images):raise ValueError("원본 사진 정보를 확인해 주세요.")
        clean["original"]={"body":_text(original.get("body",""),30000),"title":_text(original.get("title",""),200),"images":list(dict.fromkeys(images))}
        for key in ("undo","redo"):
            rows=doc.get(key,[])
            if not isinstance(rows,list) or len(rows)>MAX_HISTORY:raise ValueError("되돌리기 기록이 너무 많아요.")
            clean[key]=[]
            for row in rows:
                if not isinstance(row,dict) or row.get("template","reference") not in ("reference","clean"):raise ValueError("되돌리기 기록을 확인해 주세요.")
                clean[key].append({"blocks":_blocks(row.get("blocks")),"title":_text(row.get("title",""),200),"template":row.get("template","reference")})
        if serialize(clean)!=clean["source"]:raise ValueError("블록과 본문이 달라요. 저장 전 원고를 다시 확인해 주세요.")
        output[platform]=clean
    return output

def reconcile(body,images,title,template,previous=None,original_body=None):
    if previous and previous["source"]==body and serialize(previous)==body:return copy.deepcopy(previous)
    document=copy.deepcopy(previous) if previous else {"version":1,"undo":[],"redo":[],"template":template,"original":{"body":body if original_body is None else original_body,"title":title,"images":list(images)}}
    document["blocks"]=parse(body,photo_ids(previous) if previous else images,previous)
    document["source"]=serialize(document)
    return document

def valid_for(draft,platform):
    doc=draft.get("blog_documents",{}).get(platform)
    if not doc:return None
    field=FIELDS[platform][0]
    if doc.get("source")!=draft.get(field,"") or serialize(doc)!=doc["source"]:return None
    return doc

def view(draft,platform):
    result=dict(draft)
    if platform not in FIELDS:return result
    try:doc=valid_for(draft,platform)
    except (TypeError,KeyError,ValueError,AttributeError):doc=None
    if doc:result.update(blog=serialize(doc),images=photo_ids(doc),template=doc.get("template",draft.get("template","reference")))
    return result
