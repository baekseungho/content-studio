# 개발 이어가기

## 현재 상태

- 사용자가 회사 PC에서 네이버 글·사진 전달이 정상 작동함을 확인했습니다.
- 네이버 확장 버전은 1.5.3입니다. 글꼴 선택을 편집기 모델에 전달하고 인스타그램 필수 메모를 보존하도록 보완했습니다. 실제 네이버 적용은 사용자 재확인이 필요합니다.
- 앱은 127.0.0.1:8787의 개인용 로컬 서버입니다.

## 주요 파일

| 파일 | 역할 |
| --- | --- |
| app.py | HTTP API, OpenAI 호출, 초안·사진 저장, 인스타그램 발행 |
| static/index.html, app.js, style.css | 작성 화면·미리보기·작성 단계·결과 안내 |
| chrome-extension/editor.js | 네이버 입력. 주입되는 독립 함수 editorAction |
| chrome-extension/worker.js | 로컬 앱 연결·일회용 코드·입력 실행·결과 보고 |
| extension_bridge.py | 코드 만료·단일 사용·사진 전달·진단 기록 |
| naver_guard.py | 60초 간격·동일 초안 재입력·계정보호 잠금 |
| photo_layout.py | 사진 위치 표시 보존·누락 배치 |
| writing_style.py, tones.py, writing_templates.py | 문체 편집·줄바꿈·말투·서식 |
| media_tunnel.py | 발행용 사진만 제공하는 임시 HTTPS 연결 |

## 네이버에서 이미 해결한 문제

실제 입력은 표시 문단이 아닌 동일 출처 iframe의 contenteditable BODY에서 이뤄집니다.
부모 문서에만 execCommand를 실행하거나 contenteditable을 강제로 붙이지 않습니다.
이모지와 한글은 분리해서 입력하고, 문단이 재생성돼도 표시된 본문 전체로 반영을 확인합니다.
이모지 변형 선택자와 커서 이동을 처리합니다. 글·사진을 모두 옮긴 뒤 서식을 적용합니다.

정렬 메뉴와 옵션은 data-name=align-drop-down-with-justify를 함께 씁니다.
메뉴 버튼의 클래스 se-property-toolbar-drop-down-button과 옵션의 data-value=center를 구분해야 합니다.
data-name 접두어만으로 제외하면 실제 가운데 정렬 옵션도 사라집니다.
글자 크기 옵션은 fs15 같은 값입니다. 기본 감성 후기는 바른히피·15px·가운데 정렬입니다.

마지막 발행·로그인·CAPTCHA·본인 인증은 사용자가 공식 네이버에서 합니다.
1분 간격은 유지하며 하루 횟수 제한은 없습니다. 같은 글 재시험은 명시적으로 선택합니다.
입력이 일부만 됐을 때 자동 재전송하거나 기존 글을 지우지 않습니다.

## 앱과 문체

밝은 말투는 gpt-5.4-mini로 사진을 읽고 gpt-5.4로 글만 다듬습니다.
사진을 두 번째 단계에 재전송하지 않습니다. 문장 다듬기가 실패하면 첫 초안을 보존합니다.
사진 번호별 메모는 각 이미지와 함께 전달하며, 본문에서는 사진 번호를 설명하는 말투를 피합니다.
글 생성과 HTML 내보내기는 사진 위치 표시 [[photo:1]] 등을 보존합니다.

상단 단계 버튼은 화면 위치를 바꾸며 실제 발행을 실행하지 않습니다.
네이버 전송 완료는 발행 완료와 구분합니다. 인스타그램 전환 시 네이버 완료 상태를 재사용하지 않습니다.
성공 진단은 접어 두고 실패·부분 성공 진단은 펼칩니다.

## 인스타그램과 개인 데이터

EAA/SUAT 모양의 토큰은 통합 로그인에서 유효할 수 있습니다. 접두어만으로 무효 판정하지 않습니다.
로그인 모드에 따라 graph.facebook.com / graph.instagram.com으로 구분합니다.
사진 터널은 허용된 UUID-ig.jpg만 공개합니다. 전체 앱이나 원본 파일 경로를 공개하지 않습니다.
.env, data, .venv, cloudflared.exe는 이 저장소에 없습니다.

## 검증

README의 단위 검사·브라우저 검사·확장 전체 흐름 검사를 사용합니다.
개발 검증에는 실제 API 키가 필요 없어야 하며 모의 키를 사용합니다.
재현 편집기의 통과와 실제 네이버의 동작 확인은 구분해서 기록합니다.
수정 내용은 CHANGES.md에 남깁니다.

## Threads·영어 추가
channel_writing.py의 지침, app.py의 언어·Threads 필드, writing_style.py의 다채널 편집을 사용합니다. 스키마 변경 없이 초안 JSON에 저장합니다. Threads는 Web Intent 텍스트 전달이며 API 발행이 아닙니다. test_threads_language.py 및 browser_check.py가 새 흐름을 검사합니다. 실제 언어별 샘플은 data/qa/threads-language-samples.json에 있으며 테스트용 메모만 사용했습니다.

Threads API 발행: threads_publishing.py. Threads 전용 토큰, graph.threads.com/v1.0, form-urlencoded POST, 계정 일치 확인, TEXT/IMAGE/CAROUSEL·상태 확인·threads_publish 흐름입니다. threads_attempts는 기존 Instagram attempts와 독립적입니다. 실계정 토큰이 아직 없어 실제 발행은 미검증이며, 112개 회귀 검사와 UI 모의 발행을 통과했습니다.

체험단·Threads 소통·UI: campaigns.py에서 입력 검증·키워드/문구/태그/분량/사진 점검·활성 미션만 모델에 전달합니다. Blog 미션은 ExtensionBridge.create에서 재검사합니다. 본문 태그와 네이버 발행창 태그는 구분하며, 후자는 사용자가 태그 복사로 직접 입력합니다. 새 필드는 초안 JSON에 저장합니다. 확장 프로토콜과 도우미 버전은 1.5.3을 유지합니다. 자동 검사 122개, 화면·확장 흐름과 실제 AI의 가상 체험단 샘플을 확인했습니다. 실계정 게시물은 수정하거나 새로 발행하지 않았습니다.

장소 선택: places.py(입력/후보/자료 조사), /api/places/search 비동기 작업, selected_place와 research 초안 JSON. 장소 선택이 있을 때에는 조사와 글쓰기 요청을 분리하며 작성/다듬기 요청에는 웹 검색 도구를 주지 않습니다. source URL은 실제 도구 출처에 있어야 하며 관찰 이름과 전체 도로명/지번 주소를 선택값과 비교합니다. 주소 비교에서 본번-부번의 하이픈을 보존합니다. source의 원문을 별도 크롤링해 진위를 증명하는 검사는 아니므로 UI도 최신성 확인을 안내합니다. tests/test_places.py, tests/place_browser_check.py는 실제 외부 API 호출 없이 실패·복구·모바일을 검사합니다.

플랫폼 선택 생성: platform_writing.py. /api/generate의 platforms=[naver,instagram,tistory,threads]를 검증하고 선택한 필드만 모델에 전달/반영합니다. 구버전 클라이언트 호환을 위해 platforms 없는 요청은 기존 generate 분기를 유지합니다. tistory/tistory_title은 새 필드이고 기존 필드가 없던 초안은 migrate로 공통 blog/title을 읽습니다. selective_generation+editing_platform 저장에서는 다른 플랫폼의 본문을 다시 정규화하지 않습니다. platform_languages는 각 원고의 언어를 보존합니다. ExtensionBridge의 Tistory view와 export?platform=tistory가 해당 원고를 사용합니다. 조사 캐시는 서버에서 실제 관찰한 결과만 저장하며 15분/최대 50개, 장소·메모·필수 사실·업체 안내문이 키입니다. 신규 테스트: test_platform_generation.py, platform_browser_check.py. 확장 프로토콜/버전은 변경하지 않습니다.
