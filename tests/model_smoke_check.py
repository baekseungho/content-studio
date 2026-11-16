"""실제 유료 API 1회 호출. 수동 실행 전용. 합성 사진·가상 메모만 사용한다."""
import json
from pathlib import Path
import sys
import tempfile
from unittest.mock import patch
from PIL import Image
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import app
with tempfile.TemporaryDirectory(prefix="writing-smoke-") as temp:
    media=Path(temp)
    mid="a"*32
    Image.new("RGB",(64,64),"#93a581").save(media/(mid+".jpg"),"JPEG")
    body={"prompt":"가상의 테스트 기록이다. 초록색 컵 사진에 대한 짧은 일상 기록을 만들어 줘. 가상 테스트임을 글에 명확히 써 줘. 실제 장소·가격·운영시간·맛은 만들지 마.",
        "facts":"가상 테스트. 사진은 단색 합성 이미지다. 실제 방문이나 사용 경험은 없다.",
        "style":"","tone":"담백하고 차분하게","research":False,"images":[mid],"disclosure":"none"}
    with patch.object(app,"MEDIA",media):
        result=app.generate(body)
    assert result["title"] and result["blog"] and result["instagram"]
    assert len(result["instagram"])<=2200
    assert "http" not in result["blog"]
    target=app.DATA/"qa"/"writing-model-sample.json"
    target.parent.mkdir(exist_ok=True)
    target.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding="utf-8")
    print(json.dumps({"success":True,"generation":result["generation"],"blog_characters":len(result["blog"]),"instagram_characters":len(result["instagram"])},ensure_ascii=True))
