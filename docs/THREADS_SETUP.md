# Threads 연결 · 처음 한 번

앱의 Threads 탭에서 글과 선택한 사진을 발행할 수 있습니다. 생성과 실제 공개 발행은 별개이며, 마지막 확인 창에서 동의할 때만 API 발행을 요청합니다.

## 준비할 것

Threads 전용 사용자 토큰과 숫자 계정 ID가 필요합니다. Instagram ID·토큰을 그대로 넣지 않습니다. 기존 인스타그램 설정은 유지합니다.

1. [Meta 개발자 앱 목록](https://developers.facebook.com/apps/)에서 Threads 사용 사례를 지원하는 앱을 준비합니다. 현재 앱에서 해당 설정을 추가할 수 없다면 Threads용 앱을 별도로 만듭니다.
2. 사용할 Threads 계정을 앱의 테스트 사용자/역할로 연결합니다. 개발자 화면에서 초대를 보냈다면 해당 계정에서 수락을 완료합니다. 메뉴 이름은 Meta 화면 개편에 따라 다를 수 있습니다.
3. Threads 사용자 인증으로 `threads_basic`, `threads_content_publish` 권한의 토큰을 준비합니다. 개발자 화면에서 테스트 계정 토큰 생성 기능을 제공하면 이용하고, 그렇지 않으면 [공식 토큰 발급 절차](https://developers.facebook.com/documentation/threads/get-started/get-access-tokens-and-permissions)를 따릅니다. 앱 ID나 앱 시크릿은 사용자 액세스 토큰을 대신하지 않습니다.
4. 프로젝트의 .env에서 아래 항목을 채웁니다. 토큰은 채팅·GitHub에 올리지 않습니다.

```dotenv
THREADS_USER_ID=숫자로_된_Threads_계정_ID
THREADS_ACCESS_TOKEN=Threads_사용자_액세스_토큰
THREADS_API_VERSION=v1.0
```

계정 ID를 모르면 토큰만 먼저 입력하고 앱을 다시 실행한 뒤 Threads 연결 설정 → 계정 연결 확인을 누릅니다. 응답에서 보여주는 계정 ID와 사용자 이름이 본인 계정인지 확인하고 ID를 .env에 추가합니다. 토큰 원문은 화면에 표시하지 않습니다.

5. 앱을 종료하고 start.cmd로 다시 실행한 뒤 브라우저를 새로고침합니다. Threads 탭 → 연결 설정 → 계정 연결 확인으로 ID와 토큰이 같은 계정인지 확인합니다. 이 확인은 공개 발행 권한 전체를 검증하는 테스트는 아닙니다.
6. 사진을 포함하려면 기존 사진 전용 HTTPS 연결을 켭니다. 글만 발행할 때는 사진 포함 체크를 끄면 됩니다. 사진 연결은 인스타그램과 공유합니다.
7. 본문과 사진 순서를 확인하고 Threads에 발행하기 → 공개 발행 확인을 누릅니다. 올린 글 메뉴에서 Threads 기록도 확인할 수 있습니다.

## 실패했을 때

- 토큰 인증 실패: Instagram/Facebook 토큰이 아닌 Threads 토큰인지, 만료·권한 해제가 없는지 확인합니다.
- 계정 ID 불일치: 연결 확인이 알려주는 사용자 이름·숫자 ID를 확인합니다. 앱 ID와 계정 ID는 다릅니다.
- 권한 부족: `threads_content_publish` 동의와 앱 역할·검토 상태를 확인합니다. 다른 사용자의 계정으로 확장할 때 필요한 Meta 검토는 개인 테스트 계정 연결과 별도입니다.
- 사진 처리 실패: 사진 연결이 살아 있고 Meta에서 사진을 읽을 수 있는지 확인합니다.
- 결과 확인 필요: 실제 Threads 계정에서 먼저 확인합니다. 앱은 발행 요청 후 응답이 끊긴 글을 자동 재발행하지 않습니다.
- 토큰 갱신: 현재 앱은 자동 토큰 갱신을 구현하지 않습니다. 만료·해제 시 새 토큰을 .env에 넣고 다시 실행합니다.

## 구현·검증 범위

텍스트·단일 이미지·이미지 묶음, 컨테이너 처리 상태 확인, 공개 확인, 계정 일치 검사, 채널별 중복 방지와 발행 기록을 구현했습니다. 기존 공개 게이트웨이의 허용된 파생 JPEG만 전달합니다. 영상·예약 발행·답글 체인·OAuth 로그인·자동 토큰 갱신은 포함하지 않습니다.

현재 계정 토큰이 없어 실제 Threads 발행은 검증하지 않았습니다. 모의 API로 성공·처리 실패·계정 불일치·응답 유실·중복 방지와 UI 요청을 검사했습니다.

공식 근거: [Threads 게시물 API](https://developers.facebook.com/documentation/threads/posts), [Threads 액세스 토큰](https://developers.facebook.com/documentation/threads/get-started/get-access-tokens-and-permissions), [Meta 공식 예제](https://github.com/fbsamples/threads_api).
