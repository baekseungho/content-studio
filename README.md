# 다정 스튜디오 · Content Studio

사진과 짧은 메모로 블로그 글과 인스타그램 캡션을 만드는 개인용 로컬 앱입니다.
네이버 입력 도우미 1.4.1과 작성 단계·미리보기·페이지 디자인 개선이 포함돼 있습니다.

## 집에서 개발 이어하기

Windows, Python 3.12 이상, Git, Chrome을 준비합니다. PowerShell에서 실행하세요.

    cd D:\dev
    git clone https://github.com/baekseungho/content-studio.git
    cd content-studio
    python -m venv .venv
    .\.venv\Scripts\python.exe -m pip install -r requirements-lock.txt
    Copy-Item .env.example .env
    notepad .env
    .\start.cmd

이미 클론했다면 해당 폴더에서 git pull로 최신 코드를 받습니다.
.env가 이미 있으면 복사 명령을 생략하고 기존 설정을 유지합니다.
브라우저 주소는 http://127.0.0.1:8787 입니다.

requirements-lock.txt는 회사에서 검증한 프로젝트 의존성만 고정한 파일입니다.
requirements.txt는 허용 버전 범위를 기록합니다. 가상환경은 컴퓨터마다 새로 만듭니다.

## 로컬 설정

.env.example에는 빈 예시 항목만 들어 있습니다. 실제 값은 각 컴퓨터의 .env에 입력합니다.

| 항목 | 용도 |
| --- | --- |
| OPENAI_API_KEY | 사진 분석·글 생성 |
| OPENAI_MODEL | 사진 분석 모델. 기본 gpt-5.4-mini |
| OPENAI_WRITING_MODEL | 밝은 후기의 문장 다듬기 모델. 기본 gpt-5.4 |
| NAVER_BLOG_ID | blog.naver.com/ 뒤의 블로그 아이디 |
| INSTAGRAM_ACCOUNT_ID | 인스타그램 프로페셔널 계정의 숫자 ID |
| INSTAGRAM_ACCESS_TOKEN | 해당 계정의 발행 권한이 있는 토큰 |
| INSTAGRAM_LOGIN_TYPE | auto / unified / instagram |
| PUBLIC_MEDIA_BASE_URL | 고정 사진 HTTPS 서버 주소. 임시 연결 사용 시 비워 둠 |

키가 없어도 직접 글쓰기·사진 업로드·미리보기·초안 보관·HTML 내보내기는 사용할 수 있습니다.
설정을 바꾸면 앱을 종료한 뒤 start.cmd로 다시 실행합니다.

## 네이버 연결 · 처음 한 번

1. 평소 네이버에 로그인하는 Chrome에서 chrome://extensions를 엽니다.
2. 개발자 모드 → 압축해제된 확장 프로그램을 로드 → 이 저장소의 chrome-extension 폴더를 선택합니다.
3. 확장 버전 1.4.1을 확인하고 도구 모음에 고정합니다.
4. 다정 확장 아이콘에서 앱과 연결하기를 누릅니다.
5. 사진·메모 → 글 만들기 → 미리보기 → 블로그로 옮기기 순서로 사용합니다.

프로젝트 폴더가 바뀌었다면 Chrome에 등록된 확장도 새 chrome-extension 경로로 다시 등록하고 앱과 연결합니다.

로그인과 추가 인증은 네이버에서 직접 합니다. 마지막 발행도 네이버에서 누릅니다.
기존 내용이 있는 편집기는 덮어쓰지 않습니다. 같은 초안 재시험 옵션과 전달 코드는 도우미 옵션 안에 있습니다.
자세한 입력·서식 진단 방법은 [확장 설명서](chrome-extension/README.md)를 확인하세요.
기존 별도 자동화 브라우저 방식은 비활성화되어 있습니다.

## 인스타그램 사진 연결

Business 또는 Creator 계정과 Meta 앱의 발행 권한이 필요합니다.
통합 로그인(SUAT)은 unified, Instagram Login은 instagram 방식으로 처리합니다.
앱의 연결 설정에서 실제 토큰·계정 연결을 확인합니다.

고정 사진 서버가 없다면 Windows 64-bit용 cloudflared를 [Cloudflare 공식 다운로드](https://developers.cloudflare.com/tunnel/downloads/)에서 받아 tools/cloudflared.exe로 저장합니다.
직접 실행 파일은 Git에 포함하지 않습니다. 회사에서는 2026.11.0으로 확인했습니다.
앱의 연결 설정에서 사진 전용 임시 연결을 켭니다. 설치만으로 연결이 시작되지는 않습니다.
사진 연결은 발행용으로 허용된 JPEG 경로만 제공하며 앱 화면·API·원본 사진은 제공하지 않습니다.
인스타그램은 앱에서 발행을 확인하면 실제 계정에 게시됩니다.

## 테스트

개발용 Chromium을 설치한 뒤 실행합니다.

    .\.venv\Scripts\python.exe -m playwright install chromium
    .\.venv\Scripts\python.exe -m unittest discover -s tests -p "test_*.py"
    .\.venv\Scripts\python.exe tests\browser_check.py
    .\.venv\Scripts\python.exe tests\extension_easy_flow_check.py

위 검사는 임시 데이터와 모의 외부 서비스를 사용하며 실제 SNS에 게시하지 않습니다.
model_smoke_check.py, instagram_connection_check.py, tunnel_check.py는 실제 외부 서비스에 접속하므로 필요한 경우에만 별도로 실행합니다.

## Git에 포함되지 않는 파일

- .env 및 개인 설정: 집 컴퓨터에서 별도 설정
- data/: 사진, SQLite 초안, 발행 기록, 로그인 프로필, 진단 결과
- .venv/: 컴퓨터별 Python 가상환경
- tools/*.exe, tools/*.zip: 설치 도구와 생성한 배포 파일

코드만 GitHub로 동기화됩니다. 회사의 사진·초안까지 이어서 쓰려면 앱을 종료한 상태에서 로컬 데이터와 설정을 별도로 옮깁니다.
API 키·토큰·로그인 프로필은 저장소에 커밋하지 않습니다.
글꼴의 출처와 라이선스는 static/fonts/NOTICE.txt와 OFL.txt에 있습니다.

이어서 수정할 때는 [개발 메모](docs/DEVELOPMENT.md)와 [변경 기록](CHANGES.md)을 먼저 확인하면 됩니다.
