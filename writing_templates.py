"""사용자에게는 양식 이름만 노출하고 실제 꾸미기 값은 서버에서 관리한다."""
TEMPLATES={
 "reference":{"label":"감성 후기","align":"center","font":"나눔바른히피","font_key":"nanumbareunhipi","size":15},
 "clean":{"label":"깔끔한 정보글","align":"left","font":"나눔고딕","font_key":"nanumgothic","size":15}
}
def template_for(name):
    return dict(TEMPLATES.get(name,TEMPLATES["reference"])) if isinstance(name,str) else dict(TEMPLATES["reference"])
