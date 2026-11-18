"""Expose only a complete JPEG, even when channels prepare the same photo."""
import os
from pathlib import Path
import re
import tempfile
import threading
import time
from PIL import Image,ImageOps


_PHOTO_LOCKS=[threading.Lock() for _ in range(32)]


def prepare_photo(media,mid):
    if not isinstance(mid,str) or not re.fullmatch(r"[a-f0-9]{32}",mid):raise ValueError("사진 번호를 확인해 주세요.")
    media=Path(media)
    with _PHOTO_LOCKS[hash((str(media.resolve()),mid))%len(_PHOTO_LOCKS)]:
        return _prepare(media,mid)


def _prepare(media,mid):
    target=media/(mid+"-ig.jpg")
    fd,name=tempfile.mkstemp(prefix=mid+"-",suffix=".tmp",dir=media);os.close(fd)
    temporary=Path(name)
    try:
        with Image.open(media/(mid+".jpg")) as source:
            with ImageOps.pad(source.convert("RGB"),(1080,1350),color="#faf8f5") as image:image.save(temporary,"JPEG",quality=90)
        # Windows readers/virus scanners can briefly hold the destination open.
        for attempt,delay in enumerate((0,.02,.05,.1,.2)):
            if delay:time.sleep(delay)
            try:temporary.replace(target);break
            except PermissionError:
                if attempt==4:raise
    finally:temporary.unlink(missing_ok=True)
    return target
