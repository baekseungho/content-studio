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

상단 단계 버튼은 준비·편집·확인 화면을 전환하며 실제 발행을 실행하지 않습니다.
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


## 2026-11-19 작성 흐름 개편

현재 작성 화면은 준비·편집·확인의 세 작업 공간입니다. 상세 내용은 ../CHANGES.md의 최신 항목을 참고하세요.
static/workspace.css가 기존 style.css 다음에 적용됩니다. /workspace.css가 정적 파일 허용 목록에 포함되어 있으므로 이전 서버는 재실행해야 합니다.
workspace_step과 selected_platforms는 초안 JSON에 저장합니다. 이전 초안에는 원고가 있는 채널을 추론하며 저장 스키마를 바꾸지 않습니다.
UI 변경 후 현재 화면 검증은 workspace_browser_check.py, platform_browser_check.py, logic_browser_check.py를 기준으로 합니다. 과거 화면을 직접 누르는 다른 검사 스크립트에는 이전 두 열 화면의 선택자·모달 순서가 남아 있을 수 있습니다.
단위 검증과 새 화면 검증은 실제 SNS 발행이나 유료 AI 호출 없이 실행합니다. 실계정 편집기의 결과는 별도로 확인해야 합니다.


## 블록 문서와 사진 연결

story_document.py가 블록 검증, 레거시 본문 변환, 직렬화와 전달용 사진 선택을 담당합니다.
static/block-editor.js는 순수 변환과 블록 편집 UI, static/block-workspace.js는 기존 작성·저장·검토 흐름과의 연결입니다. static/blocks.css는 편집 UI만 꾸밉니다.
블로그 원고의 blog_documents.naver/tistory는 version=1, blocks, source, template, original, undo/redo를 저장합니다. 사진은 image_id UUID로 연결하며 source의 사진 순번은 문서 내 사진 순서입니다. prepared images 배열의 순번으로 다시 해석하지 마세요.
원고 source와 블록이 일치해야 저장합니다. 기존 클라이언트가 본문만 바꾼 경우에는 이전 문서의 사진 ID 순서로 다시 읽습니다. 다른 채널의 원고는 수정하지 않습니다.
platform_writing.view와 blog_html의 platform 인수가 확장·검사·내보내기의 공통 경계입니다. 문서에서 뺀 사진을 photo_layout으로 다시 채우지 않도록 주의하세요.
분량 보완은 현재 문서의 사진 ID만 요청에 포함합니다. 기본 전체 생성은 사용자가 준비한 사진으로 새 원고를 만듭니다.
undo/redo는 최근 20단계이며 원본은 별도로 보존합니다. 사진 파일은 편집 삭제로 지우지 않으므로 다른 채널과 되돌리기를 보호합니다.
검증: tests/test_story_document.py, tests/blocks_browser_check.py 및 README의 현재 작성 흐름 검사. 과금되는 생성과 실제 SNS 게시 없이 실행합니다.


## 체험단 조건 정리와 해결

campaign_brief.py는 외부 호출 없이 명확한 안내 조건과 정확한 원문 범위를 추출합니다. 선택형·다른 채널·제목 분량·지원 범위 밖 조건은 자동 확정하지 않습니다. 최대 60개 제안이며 일부 정리 시 이를 표시합니다.
campaign_requirements.py는 조건 충돌, 원문 확인 기록, 직접 확인 상태와 경험 메모를 검증합니다. read_meta 결과는 초안 JSON에 저장하며 모델 컨텍스트에는 넣지 않습니다.
새 필드는 campaign_forbidden, campaign_manual_checks/state, campaign_brief_review, campaign_experience입니다. 직접 확인은 원고·조건·사진의 지문과 채널로 구분하므로 편집하면 다시 확인해야 합니다. 지문은 자동 사실 검증을 뜻하지 않습니다.
안내를 확인한 뒤에는 생성 모델에 원문 전체를 다시 보내지 않고 구조화된 확정 조건만 전달합니다. 미확정 업체 요구를 자동 필수 조건으로 만들지 마세요.
/api/campaign/parse와 /api/campaign/check는 동기 로컬 검사입니다. /api/generate 및 /api/blog/expand는 조건 충돌을 작업 할당 전에 차단합니다. 저장은 in-range 분량 조건의 충돌을 임시로 허용하되 생성·확장 전달은 허용하지 않습니다.
static/campaign-ui.js와 campaign.css가 선택·근거·조건 충돌·미션 해결 화면을 담당합니다. 입력/네비게이션/원고 스냅샷을 비교해 이전 응답을 버리며 확인되지 않은 결과를 완료로 표시하지 않습니다.
검증: tests/test_campaign_brief.py, campaign_missions_browser_check.py 및 기존 작성·블록·플랫폼·저장 충돌 검사. 실제 유료 생성이나 SNS 게시 없이 실행합니다.


## 부분 수정과 채널별 내 말투

writing_edits.py는 선택 범위·UTF-16 인덱스 검증, 현재 채널의 예상 결과 계산, 전후 미션 비교와 텍스트 단일 호출을 담당합니다. /api/writing/refine은 검증 후 기존 writing 작업 배타 잠금을 사용하며 /api/writing/validate는 AI 없는 로컬 검사입니다. 둘 다 원고를 저장하거나 게시하지 않습니다.
모델에 사진·다른 채널 원고·되돌리기·초기 원본·미확정 업체 안내를 보내지 않습니다. 제목 추천만 현재 본문 일부를 참고합니다. OPENAI_EDIT_MODEL 미설정 시 OPENAI_MODEL(기본 gpt-5.4-mini)을 사용하며 최대 출력 예산은 선택 길이에 따라 1,800~4,800, 제목 추천은 1,600입니다. 명시적인 새 요청당 한 번 호출하며 자동 재요청·후속 고가 모델 호출은 없습니다.
검사는 숫자·단위·링크·명시된 업체 이름·제공 표시·필수 문구·키워드 수·영문 혼입·글자 수의 변화와 새 위반을 다룹니다. 의미 보존/사실 진위를 증명하지 않습니다. 기존 미달은 계속 경고하고 전체 게시 검사를 대체하지 않습니다. 필수 숫자를 의도적으로 바꾸려면 비교 제안이 아니라 원문을 직접 편집해야 합니다.
static/writing-ui.js는 미리보기와 적용을 분리하고 원고/채널/이동/조건/말투 스냅샷이 같을 때만 선택 부분을 현재 문서에 적용합니다. 블로그는 BlockWorkspace.editor.mutate로 기존 기록과 사진 ID를 보존합니다. SNS 부분 수정 기록은 현재 브라우저 작업 중 최근 20회이며 원고 이동·재열기 시 초기화합니다.
창을 닫으면 결과를 적용하지 않고 로컬 대기를 멈춥니다. 이미 시작한 외부 호출 자체를 취소하는 기능은 아니며 서버는 완료까지 writing 잠금을 유지합니다. 오래된 응답이 새 화면을 변경하거나 새 작업의 UI 잠금을 해제하지 않도록 주의하세요.
voice_profiles.py는 DATA/voice-profiles.json의 revision 비교·원자적 저장과 한 채널당 한 프로필을 담당합니다. draft.voice_styles는 원고별 스냅샷입니다. 기존 원고에 전역 기본값을 덮어쓰지 않으며 새 빈 원고에만 저장한 기본값을 적용합니다. 샘플 분석은 로컬 휴리스틱이며 인격/경험 분석이나 LLM 호출이 아닙니다.
새 API와 정적 writing-ui.js/writing.css를 반영하려면 서버를 재실행해야 합니다. tests/test_writing_edits.py, tests/test_writing_api.py, tests/writing_browser_check.py는 실제 AI·SNS 호출 없이 보호 조건과 UI 경계를 검증합니다.


## 채널별 사진과 블로그 활용 · E

channel_media.py가 channel_media.instagram/threads(version=1, images, frame, adjustments)를 검증합니다. root images는 준비 사진이며 SNS는 명시된 빈 목록도 보존합니다. 블로그는 blog_documents의 사진 ID를 계속 사용합니다. platform_writing.view와 ThreadsPublisher의 channel view가 발행 경계입니다.
Instagram은 동일 프레임(1080×1350 / 1080×1080 / 1080×566), 사진별 contain/cover와 centering(0~100)을 사용합니다. 새 Threads 설정은 original 비율을 기본으로 하며 문서화된 폭/비율 범위로 JPEG를 만듭니다. 기존 SNS 원고의 클라이언트 마이그레이션은 이전 portrait/contain 모습을 유지합니다. 설정 없는 API/초안은 기존 publish_media.prepare_photo 경로와 동작을 유지합니다.
/api/channel-media/preview는 인증된 로컬 요청에 JPEG data URL을 반환하고 파일·공개 연결·AI 호출을 만들지 않습니다. 발행은 같은 render 함수로 생성한 사진 ID-ig/th-옵션해시.jpg를 사용합니다. 이름에 모든 렌더 옵션과 버전을 반영하며 생성한 결과를 덮어쓰지 않습니다. MediaTunnel.allow_variant는 완성한 파일 하나의 정확한 이름만 허용합니다. 기존 allow(mid)는 기존 -ig.jpg에만 적용되며 새 파일을 포괄 허용하지 않습니다.
생성의 channel_images는 요청한 SNS의 사진만 허용합니다. 사진 목록별로 플랫폼을 묶고 다를 때만 작업 안에서 순서대로 생성합니다. 각 묶음의 모델에는 해당 사진만 보내고 모든 요청이 성공한 뒤 결과를 반영합니다. 다른 채널의 원고와 편집 기록은 보내지 않습니다.
channel_adaptation.py의 /api/channel/adapt는 사용자가 source_checked=true로 확인한 블로그 1편으로 요청한 SNS 한 편만 제안합니다. 사진/검색/기존 대상 원고는 모델에 보내지 않고 텍스트 모델 한 번만 호출합니다. /validate는 로컬 검사이며 저장·발행하지 않습니다. 수량 검사는 알려진 단위의 한영 표기 및 원→천원/만원 표기를 다루며 의미 보존·사실 검증을 보장하지 않습니다.
channel_origins는 바탕 블로그 platform/title/fingerprint이며, 이후 원본과 자동 동기화된다는 뜻이 아닙니다. 채널의 일반 새 생성 시 출처 기록을 지우고 이전 원고로 되돌리면 복구합니다.
static/channel-ui.js와 channels.css는 사진 선택·프레임·슬라이드·비교 제안을 담당합니다. 사진 변경은 현재 사진 ID를 기준으로 슬라이드를 유지하고, 첫 장 이동/맞춤 적용 시 해당 사진을 보여 줍니다. 사진 되돌리기는 현재 브라우저 작업의 최근 20회이고 초안의 최종 선택/맞춤은 서버 저장과 복구 데이터에 보관합니다.
검증: tests/test_channels.py, test_writing_api.py, channels_browser_check.py 및 기존 작성/블록/부분 수정/체험단/플랫폼/충돌 검사. AI·SNS 요청은 모의 처리합니다. 실제 계정의 최종 표시/발행은 별도 확인이 필요합니다.
참고 규격: [Meta Instagram media](https://developers.facebook.com/documentation/instagram-platform/instagram-graph-api/reference/ig-user/media/), [Instagram 콘텐츠 발행](https://developers.facebook.com/documentation/instagram-platform/content-publishing), [Threads 이미지 규격](https://developers.facebook.com/documentation/threads/posts#media-specifications). 검토일 2026-11-19. 앱의 사진 한도 10장은 API 한도 확장과 독립적으로 유지합니다.


## 내 글과 다시 쓰기 · F

story_library.py가 library_meta, story_reviews, publish_snapshots, handoff_events를 담당합니다. ensure는 개별 CREATE 문을 사용하며 외부 발행 트랜잭션 안에서 executescript로 조기 커밋하지 않습니다. 원래 drafts 스키마와 데이터는 유지합니다.
GET /api/library는 페이지별 요약/상태만 반환하고 /api/library/story/:id는 한 이야기의 동일한 투영입니다. q/platform/state/scope/sort와 offset/limit(최대 48)을 검증합니다. 필터와 내용 지문 비교는 현재 로컬 SQLite 작업실에서 수행합니다. 대규모 다중 사용자 검색/권한/보관 정책은 별도 운영 설계 범위입니다.
/api/library/meta는 label/starred/archived와 revision으로 비교 갱신합니다. 별칭은 공개 게시 제목을 바꾸지 않으며 archive는 soft 상태입니다. /open은 최근 이어 쓴 시각만 갱신합니다. /review는 confirmed=true, 저장 버전 일치, 원고 사전 검사와 체험단 직접 확인을 요구합니다. 원고 변경을 저장할 때 확인 도장을 클라이언트에서 전달하거나 자동 복제하지 않습니다.
원고 확인 지문은 해당 채널의 본문·제목·실제 사진·사진 설정·언어·제공 표시·관련 사실/장소와 블로그 미션/수동 확인을 반영합니다. 원고가 정확히 되돌아오면 이전 확인과 일치할 수 있습니다. 모델의 사실 검증이나 외부 계정 발행 권한 검증을 뜻하지 않습니다.
Instagram/Threads는 외부 호출에 실제 사용하는 스냅샷을 attempts와 같은 트랜잭션에 기록합니다. 수정된 현재 원고를 과거 발행 완료로 표시하지 않습니다. 기존 지문 없는 발행 기록도 이전 기록으로 안내합니다. unresolved 시도는 편집으로 숨기지 않습니다.
ExtensionBridge의 선택적 record_report 콜백은 보고 수락 전에 ready/partial/failed/blocked를 기록합니다. 보고 토큰은 해시만 저장하며 같은 결과의 재보고는 중복 기록하지 않습니다. 기록 실패 시 보고 요청을 버리지 않아 재시도할 수 있습니다. ready는 편집기 입력이고 발행 완료가 아닙니다. 구버전 guard.completed는 이전 입력 기록만 증명하므로 현재 버전 완료로 추정하지 않습니다.
reusable_kits.py는 타입별 allowlist만 저장합니다. brand는 업체 이름/장소, tags는 태그, campaign은 구조화된 키워드·분량·횟수·사진 수·태그·금지 표현입니다. 경험·제공 내역·원고·사진·기한·필수 주장·확인 상태는 금지합니다. /api/kits/preview는 선택 그룹과 재확인, 기존 태그 합치기 및 조건 충돌을 검사하고 patch/changes만 반환합니다. 원고를 저장하지 않습니다.
static/library-ui.js와 kits-ui.js는 async 응답/이동/편집 순서를 확인해 취소한 요청을 버립니다. 불러온 설정 되돌리기는 해당 필드만 복구하고 다른 메모는 보존합니다. 저장 묶음과 메타데이터는 revision 충돌을 안내하며 입력은 유지합니다.
/api/library/thumb/:image-id는 로컬 전용 200px JPEG와 최대 64개의 메모리 캐시를 사용합니다. 원본을 덮어쓰거나 파일을 계속 생성하거나 공개 게이트웨이에 등록하지 않습니다.
손상된 JSON/문서 구조는 기존 원본을 유지하고 읽기 안내를 반환합니다. 한 레코드의 문제로 전체 목록을 숨기지 않습니다. 삭제·수정으로 자동 복구하지 않습니다.
검증은 tests/test_story_library.py, test_library_api.py, library_browser_check.py와 기존 7종 브라우저 검사입니다. 실제 AI·SNS는 호출하지 않습니다. 사용자 관찰과 실계정 결과 확인은 별도 검증입니다.


## G · 첫 사용 도움말과 중단 복구

static/workspace-help.js/css는 선택적 도움말, 모달 내부에서만 동작하는 예시, 네트워크/잘못된 JSON 응답 안내, 연결 확인(GET /api/status), 로컬 텍스트 파일·클립보드 거절 대체 화면을 제공합니다. 예시와 화면 상태 진단은 원고를 서버에 보내지 않습니다. 진단은 개수·단계·플랫폼·저장/오류 분류만 allowlist로 출력합니다. 텍스트 내보내기는 현재 채널의 제목/본문이며 사진이나 완전한 백업이 아닙니다.

static/generation-recovery.js는 전체 생성/블로그 분량 보완의 job ID를 받은 뒤 sessionStorage에 버전·선택 채널·요청 입력 allowlist를 저장합니다(700k 문자 상한). 다른 채널의 원고·키·발행/확인 기록은 넣지 않습니다. 탭별 키이므로 다른 탭의 글 요청을 자동으로 가져오지 않습니다. 부분 수정/채널 변환의 취소한 제안이나 SNS 발행은 이 기능에서 재개하지 않습니다.

이전 요청이 남으면 명시적 결과 조회/정리 전에 새 전체 생성 요청을 차단합니다. 조회는 GET /api/jobs/:id만 사용하고 running/done/failed/job_missing을 구분합니다. 서버 작업은 기존 메모리 보관 정책을 유지하며 재시작 후 영구 복구를 보장하지 않습니다. 요청 ID 응답을 받기 전에 탭을 닫은 경우에도 복구할 수 없습니다. 결과 조회에서 생성/발행/공개 연결을 자동 재시도하지 않습니다.

복구 원고는 새 id=null 이야기로 사용자가 명시적으로 가져옵니다. 사진은 원본 ID와 채널 선택을 보존하며 블로그 문서를 새로 구성합니다. 요청하지 않은 플랫폼의 응답은 적용하지 않고 수동 미션의 정의는 유지하지만 확인 상태는 비웁니다. 현재 원고는 LibraryUI.leaveGuard로 보호합니다. 정상 적용 후 로컬 원고 복구 사본이 저장된 경우에만 job 참조를 제거하고, quota 실패 시 안내를 유지합니다. 현재 이야기를 실제 보관한 경우에도 참조를 정리합니다. 닫은 모달과 오래된 요청 응답은 현재 작업을 변경할 수 없습니다.

검증: tests/test_recovery_api.py와 tests/recovery_browser_check.py. 기존 8종 브라우저 검사와 전체 unittest 회귀를 함께 실행합니다. 실계정 발행/편집기, 실제 AI 품질, 초심자 사용성 관찰은 별도 검증입니다.
