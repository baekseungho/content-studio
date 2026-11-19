"""사진 위치 표시를 보존하고, 빠진 사진만 문단 사이에 분산한다."""
import math
import re

def photo_layout(body,count,fill_missing=True):
    used=set()
    def marker(match):
        index=int(match[1])
        if not 1<=index<=count or index in used:
            return ""
        used.add(index)
        return "\n\n[[photo:"+str(index)+"]]\n\n"
    body=re.sub(r"\[\[photo:(\d+)\]\]",marker,body).strip()
    missing=[i for i in range(1,count+1) if i not in used] if fill_missing else []
    if not missing:
        return re.sub(r"\n{3,}","\n\n",body)
    parts=[part.strip() for part in re.split(r"\n\s*\n",body) if part.strip()]
    if len(parts)==1:
        lines=[line.strip() for line in parts[0].splitlines() if line.strip()]
        if len(lines)>1:
            parts=lines
        else:
            sentences=[part.strip() for part in re.split(r"(?<=[.!?。])\s+",parts[0]) if part.strip()]
            if len(sentences)>1:
                parts=sentences
    if not parts:
        return "\n\n".join("[[photo:"+str(i)+"]]" for i in missing)
    slots={}
    for rank,index in enumerate(missing):
        position=max(0,math.ceil((rank+1)*len(parts)/(len(missing)+1))-1)
        slots.setdefault(position,[]).append(index)
    output=[]
    for position,part in enumerate(parts):
        output.append(part)
        output.extend("[[photo:"+str(i)+"]]" for i in slots.get(position,[]))
    return "\n\n".join(output)
