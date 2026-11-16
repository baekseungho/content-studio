# 선택 설치 도구

인스타그램 사진 전용 임시 HTTPS 연결을 쓸 때만 cloudflared.exe가 필요합니다.
[Cloudflare 공식 다운로드](https://developers.cloudflare.com/tunnel/downloads/)에서 Windows 64-bit 실행 파일을 받아 이 폴더에 cloudflared.exe로 저장합니다.
바이너리와 생성한 ZIP은 Git에서 제외됩니다.

네이버 확장은 chrome-extension 폴더를 그대로 로드합니다. ZIP을 만들려면 저장소 루트에서 실행합니다.

    Compress-Archive -Path .\chrome-extension\* -DestinationPath .\tools\dajeong-naver-extension.zip -Force
