# PC에서 실행하기 — Windows 10/11

이 ZIP은 소스 프로그램입니다. Python 설치와 최초 의존성 다운로드가 필요합니다. 실제 네이버 등록은 아직 검증 전이므로 본인 테스트용 카페에서 미리보기부터 확인하세요.

## 1. Python 설치

[Python 3.12.10 Windows 64비트 설치 프로그램](https://www.python.org/ftp/python/3.12.10/python-3.12.10-amd64.exe)을 받아 설치합니다. 설치 화면에서 `Add python.exe to PATH`와 Python launcher 설치 옵션을 선택하세요. 이미 Python 3.12 64비트가 설치되어 있다면 생략할 수 있습니다. 다른 Python 버전은 삭제하지 않아도 됩니다. 이 설치 파일은 `py -3.12`로 3.12를 명시적으로 선택합니다.

## 2. ZIP 압축 해제 및 설치

ZIP 전체를 일반 폴더(예: 바탕화면의 `navercafe-auto`)에 압축 해제합니다. ZIP 내부에서 바로 실행하지 마세요.

`pc` 폴더의 `01-install.bat`을 더블클릭합니다. Chromium과 필요한 패키지를 다운로드하므로 인터넷 연결이 필요합니다. `Installation complete`가 나오면 설치 완료입니다. 오류가 나오면 해당 창의 오류를 확인하세요. 관리자 권한은 필요하지 않습니다.

### 이전 설치에서 aiohttp 오류가 났다면

수정된 ZIP을 **새 폴더**에 압축 해제하고 `01-install.bat`을 실행하세요. PC에 필요 없는 `aiohttp`는 기본 설치에서 제외했습니다. 새 설치는 `.venv-pc`를 사용하므로 예전 `.venv`와 충돌하지 않습니다. C 컴파일러를 설치할 필요가 없습니다. [1/4] 단계에서 멈추면 위 Python 3.12 64비트 설치 프로그램을 먼저 설치하세요.

## 3. 로그인

`pc/02-login.bat`을 더블클릭합니다. 열린 브라우저에서 네이버에 직접 로그인하고 추가 인증을 완료합니다. 로그인 후 **명령 창으로 돌아와 Enter**를 누릅니다. `로그인 세션 저장`이 표시되면 성공입니다.

`.naver-session.json`은 로그인 권한이 있는 비밀 파일입니다. 공유·업로드하지 마세요. Windows에서는 해당 폴더에 대한 다른 사용자의 접근 권한도 제한하세요. 세션 만료 시 02-login.bat을 다시 실행합니다. 비밀번호를 배치 파일이나 채팅에 입력하지 마세요.

## 4. 게시글 미리보기

`body.txt`를 메모장으로 열어 본문을 작성하고 UTF-8로 저장합니다.

`pc/03-command-prompt.bat`을 더블클릭하고 아래 명령의 카페 ID, 게시판 ID, 제목을 실제 값으로 바꾸어 입력합니다.

```bat
navercafe post --club-id 123456 --menu-id 10 --title "테스트 제목" --body-file body.txt
```

카페 ID와 게시판 ID는 게시판 주소의 `clubid`, `menuid` 값 또는 `/cafes/숫자/menus/숫자`에서 확인하세요. 프로그램에서 카페 목록을 자동으로 가져오지는 않습니다.

`artifacts/post-preview.png`가 만들어지면 열어 입력 내용을 확인합니다. 이 단계에서는 등록하지 않습니다. 실제 등록하려면 같은 명령 끝에 `--submit`을 붙입니다.

```bat
navercafe post --club-id 123456 --menu-id 10 --title "테스트 제목" --body-file body.txt --submit
```

브라우저를 보며 실행하려면 `navercafe` 다음에 `--headed`를 넣습니다.

## 5. 댓글 미리보기 및 등록

`comment.txt`에 댓글을 UTF-8로 저장하고 실제 게시글 주소로 바꿔 실행합니다.

```bat
navercafe comment --url https://cafe.naver.com/mycafe/123 --body-file comment.txt
```

`artifacts/comment-preview.png`를 확인한 뒤 실제 등록하려면 끝에 `--submit`을 붙입니다.

```bat
navercafe comment --url https://cafe.naver.com/mycafe/123 --body-file comment.txt --submit
```

정상 등록 여부는 카페에서도 직접 확인하세요. 등록 후 오류가 나오더라도 먼저 카페를 확인해야 중복 작성을 피할 수 있습니다. 네이버 화면 변경이나 카페 가입·작성 권한에 따라 동작하지 않을 수 있습니다.

## macOS / Linux

Python 3.11 이상 설치 후 압축 해제한 폴더에서 터미널을 열어 실행합니다.

```sh
python3 -m venv .venv
source .venv/bin/activate
python -m pip install .
python -m playwright install chromium
navercafe login
```

로그인 후 같은 터미널에서 위 게시글·댓글 명령을 실행하면 됩니다.

## 검증 범위

Linux Chromium에서 웹 입력·로그인 세션 저장·재사용 등 모의 테스트 5개가 통과했습니다. Windows 배치 파일과 실제 네이버 로그인·등록은 이 클라우드에서 검증하지 못했습니다. 일반 PC에서는 클라우드 프록시 CA 등록이나 원격 로그인 서버가 필요하지 않습니다.
