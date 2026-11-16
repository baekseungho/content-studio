"""블로그의 자동 출처 문법 정리. 출처 데이터는 초안의 sources에 별도 보관."""
import re

def clean_blog(value):
    value=re.sub(r"[][^\n]*?","",value)
    value=re.sub(r"cite[^]*","",value)
    # 검색 인용은 표시 이름도 제외한다. 일반 마크다운 링크는 텍스트만 유지.
    pattern=r"\[([^\]\n]+)\]\(\s*https?://[^\s\n]*?\)"
    def label(match):
        text=match[1]
        return "" if re.fullmatch(r"(?:www\.)?[\w.-]+\.[a-zA-Z]{2,}(?:/\S*)?",text) else text
    value=re.sub(pattern,label,value)
    value=re.sub(r"https?://[^\s<>]+","",value)
    value=re.sub(r"\[\s*\]|\(\s*\)|\\\(|\\\)","",value)
    value=re.sub(r"(?m)^\s*[-*]\s*$","",value)
    value=re.sub(r"(?m)^\s*[\\()[\]]+\s*$","",value)
    value=re.sub(r"[ \t]+([,.!?。])",r"\1",value)
    value=re.sub(r"\n{3,}","\n\n",value)
    return value.strip()
