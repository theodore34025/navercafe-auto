# 네이버 카페 자동 작성

Python 3.11 이상과 Playwright Chromium을 사용하는 CLI입니다. 로그인 세션을 저장한 뒤 게시글 또는 댓글 한 건을 작성합니다. 기본 동작은 **등록 전 미리보기**이며 `--submit`을 지정해야 실제로 등록합니다. 예약 실행·대량 등록·이미지 첨부는 지원하지 않습니다.

## 설치

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -e .
python -m playwright install chromium
```

Linux에서 브라우저 시스템 라이브러리가 없으면 관리자 권한으로 `python -m playwright install-deps chromium`을 실행하세요.

## 클라우드에서 직접 로그인

별도 데스크톱이나 VNC 없이 Chromium 화면을 웹으로 전달합니다. 화면 클릭, 키보드, 스크롤, 드래그, 한글·붙여넣기 입력 도구가 있습니다.

```bash
cd /workspace/navercafe-auto
source .venv/bin/activate
navercafe remote-login --port 8765
```

1. 본인만 접근할 수 있는 **SSH 포트 전달 또는 인증된 HTTPS 리버스 프록시**로 서버의 8765번 포트에 연결합니다. 기본 바인딩은 `127.0.0.1`입니다. 포트 전달 기능이 없는 환경에서는 먼저 외부 접속 경로를 마련해야 합니다. 현재 온보딩 UI에는 로컬 포트 미리보기 기능이 없으므로 이 명령만으로 채팅에 접속 화면이 생기지는 않습니다.
2. 서버 터미널에서 `.remote-login/access.json`의 `token` 항목을 확인하여 웹 화면의 **접속 코드**에 입력합니다. 이 파일을 채팅·Git에 올리지 마세요.
3. **로그인 화면 열기**를 누른 뒤 표시된 네이버 화면에서 직접 로그인하고 추가 인증을 완료합니다. 한글이나 붙여넣기가 필요하면 원격 화면의 입력 칸을 클릭한 다음 아래 입력 도구를 사용합니다.
4. **로그인 완료 · 세션 저장**을 누릅니다. 로그인 확인에 성공한 경우에만 `.naver-session.json`을 원자적으로 저장하며, 파일 권한은 본인 읽기·쓰기(`0600`)입니다.
5. **원격 브라우저 종료**를 누릅니다. 이후 아래 CLI 명령은 저장된 세션을 사용합니다.

서버를 재실행하면 접속 코드는 바뀝니다. 웹 연결 인증은 30분 뒤 만료되며, 조작이 없으면 15분 뒤 원격 브라우저를 종료합니다. 서버 종료는 터미널에서 `Ctrl+C`로 수행합니다. 화면·키 입력·비밀번호는 파일이나 요청 로그에 기록하지 않습니다. 저장된 세션에는 쿠키 등 로그인 권한이 들어 있으므로 비밀 파일로 취급하세요. 세션이 만료되면 다시 로그인합니다.

다른 세션 경로를 사용하려면 `navercafe --session /safe/session.json remote-login`으로 시작하고 게시글·댓글 명령에도 같은 `--session`을 지정합니다. `--host` 변경은 이미 보안 HTTPS 프록시가 구성된 환경에서만 사용하세요. 일반 HTTP로 인터넷에 노출하지 마세요. 리버스 프록시는 `Host`를 유지하고 `X-Forwarded-Proto: https`를 설정해야 하며, 로그인 요청의 본문을 기록하지 않아야 합니다.

### 화면이 있는 PC에서 로그인

```bash
navercafe login
```

브라우저에서 직접 로그인·추가 인증을 마친 뒤 터미널에서 Enter를 누릅니다. 이 방법도 같은 세션 파일을 저장합니다.

### 현재 클라우드의 접속 제한

네이버 HTTPS 접속 자체는 가능하지만 Chromium에서 `ERR_CERT_AUTHORITY_INVALID`가 확인되었습니다. 환경이 제공하는 프록시 CA를 Chromium의 NSS 신뢰 저장소에 등록하는 작업은 지속적인 신뢰 설정 변경으로 자동 승인 검토에서 차단되었습니다. 사용자 승인 전까지 이 설정을 바꾸거나 인증서 검증을 끄지 않습니다. 원격 화면 서버와 입력·세션 저장 기능은 모의 네이버 화면에서 검증했습니다. 실제 로그인에는 CA 신뢰 문제 해결과 사용자에게 연결되는 보안 웹 접속 경로가 모두 필요합니다.

## 게시글

카페 ID와 게시판 ID는 해당 카페 게시판 주소의 `clubid`, `menuid` 값으로 확인할 수 있습니다. 본문은 UTF-8 텍스트 파일로 준비하세요.

```bash
navercafe post --club-id 123456 --menu-id 10 --title '게시글 제목' --body-file body.txt
# artifacts/post-preview.png를 확인한 뒤 실제 등록:
navercafe post --club-id 123456 --menu-id 10 --title '게시글 제목' --body-file body.txt --submit
```

## 댓글

```bash
navercafe comment --url https://cafe.naver.com/카페영문주소/글번호 --body-file comment.txt
navercafe comment --url https://cafe.naver.com/카페영문주소/글번호 --body-file comment.txt --submit
```

위 주소의 카페영문주소와 글번호를 실제 값으로 바꾸세요. URL은 `https://cafe.naver.com/mycafe/123` 형태여야 합니다. 화면을 보려면 명령 앞에 `--headed`를 사용합니다. 세션 경로도 명령 앞에 지정합니다.

```bash
navercafe --session /safe/session.json --headed comment --url https://cafe.naver.com/mycafe/123 --body-file comment.txt
```

미리보기 이미지에도 개인 정보가 포함될 수 있습니다. 본인이 이용 권한을 가진 카페에서 운영 규칙에 따라 사용하세요. 등록 요청은 자동 재시도하지 않습니다. 시간 초과·결과 확인 실패가 발생하면 **카페에서 등록 여부를 확인한 후** 다시 실행하세요.

## 검증 및 현재 한계

```bash
python -m unittest discover -s tests -v
```

테스트는 Chromium에서 모의 편집기와 iframe 댓글 입력, URL 검증, 원격 화면 접근 제어, 웹 화면의 마우스·키보드·한글 입력, 로그인 세션 저장과 재사용을 확인합니다. 실제 네이버 화면에서 로그인·게시글·댓글 등록은 아직 검증하지 않았습니다. 화면 구조와 등록 API 응답이 바뀌면 선택자 또는 응답 검증을 수정해야 할 수 있습니다. 로그인 세션, 카페 가입·쓰기 권한, 추가 인증 여부에 따라 실행이 제한됩니다. 이 도구는 추가 인증을 우회하지 않습니다.

클라우드에서는 `remote-login`으로 원격 화면을 사용하거나, PC에서 로그인한 세션을 안전하게 가져와 사용할 수 있습니다. 추가 인증의 팝업 창은 지원하지 않으므로 같은 창 또는 모바일 인증으로 완료할 수 없는 경우 PC 로그인 방식을 사용하세요.

### 이 클라우드 환경

설치된 `/usr/bin/chromium`을 자동으로 사용합니다. 별도 Chromium 다운로드는 필요하지 않습니다. 다른 브라우저 경로는 `NAVER_BROWSER_EXECUTABLE` 환경 변수로 지정할 수 있습니다.

```bash
cd /workspace/navercafe-auto
source .venv/bin/activate
navercafe --help
python -m unittest discover -s tests -v
```

재현 가능한 의존성 설치는 `UV_CACHE_DIR=/workspace/.cache/uv uv sync --frozen`을 사용합니다.
