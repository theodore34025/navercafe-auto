from __future__ import annotations

import argparse
import os
import re
import shutil
import sys
import time
from pathlib import Path
from urllib.parse import urlsplit

from playwright.sync_api import TimeoutError as BrowserTimeout, sync_playwright

from .session import save_state


class AutomationError(RuntimeError):
    pass


def launch_browser(pw, *, headless=True):
    executable = os.environ.get("NAVER_BROWSER_EXECUTABLE") or shutil.which("chromium")
    return pw.chromium.launch(headless=headless, executable_path=executable)


def article_url(value: str) -> str:
    parsed = urlsplit(value)
    if (parsed.scheme != "https" or parsed.hostname != "cafe.naver.com"
            or parsed.username or parsed.password or parsed.port
            or not re.fullmatch(r"/[A-Za-z0-9_-]+/[0-9]+/?", parsed.path)
            or parsed.query or parsed.fragment):
        raise argparse.ArgumentTypeError("https://cafe.naver.com/카페주소/글번호 형식을 사용하세요.")
    return value


def positive_id(value: str) -> str:
    if not value.isascii() or not value.isdigit() or int(value) < 1:
        raise argparse.ArgumentTypeError("양의 정수 ID를 입력하세요.")
    return value


def read_text(path: str) -> str:
    text = Path(path).read_text(encoding="utf-8").strip()
    if not text:
        raise AutomationError("본문 파일이 비어 있습니다.")
    return text


def first_visible(page, selectors: list[str]):
    # Editors can initialize after the title field or article container appears.
    deadline = time.monotonic() + 20
    while time.monotonic() < deadline:
        for frame in page.frames:
            for selector in selectors:
                for locator in frame.locator(selector).all():
                    if locator.is_visible():
                        return locator
        page.wait_for_timeout(100)
    raise AutomationError("입력 요소를 찾지 못했습니다. 로그인·카페 권한 또는 네이버 화면 변경을 확인하세요.")


def fill_editor(page, text: str):
    editor = first_visible(page, [".se-component-content [contenteditable='true']", ".se-text-paragraph[contenteditable='true']", ".se-content [contenteditable='true']", "body[contenteditable='true']"])
    editor.click()
    editor.fill(text)


def open_article(page, url: str):
    page.goto(url, wait_until="domcontentloaded")
    # Modern articles live in cafe_main; some versions use the top-level page.
    try:
        page.locator("iframe#cafe_main").wait_for(state="attached", timeout=10000)
        frame = page.frame_locator("iframe#cafe_main")
        frame.locator(".ArticleContentBox, .article_viewer, .CommentWriter").first.wait_for(timeout=20000)
    except BrowserTimeout:
        page.locator(".ArticleContentBox, .article_viewer, .CommentWriter").first.wait_for(timeout=10000)


def prepare_post(page, club: str, menu: str, title: str, body: str):
    page.goto(f"https://cafe.naver.com/ca-fe/cafes/{club}/menus/{menu}/articles/write", wait_until="domcontentloaded")
    page.locator("textarea[placeholder*='제목'], input[placeholder*='제목']").first.wait_for(timeout=25000)
    first_visible(page, ["textarea[placeholder*='제목']", "input[placeholder*='제목']"]).fill(title)
    fill_editor(page, body)


def prepare_comment(page, url: str, body: str):
    open_article(page, url)
    writer = first_visible(page, [".CommentWriter textarea", "textarea.comment_inbox_text", "textarea[placeholder*='댓글']"])
    writer.fill(body)


def submit(page, kind: str):
    selectors = (["a.BaseButton:has-text('등록')", "button:has-text('등록')"] if kind == "post"
                 else [".CommentWriter .btn_register", ".CommentWriter a:has-text('등록')", ".CommentWriter button:has-text('등록')"])
    button = first_visible(page, selectors)
    # Never retry a mutation: a lost response can still mean the server accepted it.
    with page.expect_response(lambda response: response.request.method == "POST" and
                              bool(re.search(r"/articles(?:[/?]|$)", response.url)), timeout=30000) as pending:
        button.click()
    response = pending.value
    if not response.ok:
        raise AutomationError(f"등록 요청 HTTP {response.status}. 중복 방지를 위해 자동 재시도하지 않습니다.")
    try:
        result = response.json()
    except ValueError:
        raise AutomationError("서버 응답을 해석할 수 없습니다. 카페에서 결과를 확인하세요.")
    if not isinstance(result, dict) or result.get("error") or result.get("errorCode") or result.get("code") not in (None, 0, "0", "SUCCESS", 200, "200"):
        raise AutomationError("서버가 등록을 거절했거나 결과 형식이 변경되었습니다. 카페에서 결과를 확인하세요.")
    # An HTTP success alone does not establish a successful application write.
    payload = result.get("result")
    if not isinstance(payload, dict) or not any(payload.get(key) for key in ("articleId", "commentId", "article", "comment")):
        raise AutomationError("등록 응답에서 생성 ID를 확인하지 못했습니다. 재실행 전 카페에서 결과를 확인하세요.")
    print("서버에서 등록 결과를 확인했습니다. 카페에서도 내용을 확인하세요.")


def parser():
    p = argparse.ArgumentParser(description="네이버 카페 게시글·댓글 작성 (기본: 미리보기)")
    p.add_argument("--session", default=".naver-session.json", help="로그인 세션 파일 (비밀정보)")
    p.add_argument("--headed", action="store_true", help="브라우저 표시; 데스크톱 환경 필요")
    sub = p.add_subparsers(dest="command", required=True)
    sub.add_parser("login", help="브라우저에서 직접 로그인 후 세션 저장")
    remote = sub.add_parser("remote-login", help="클라우드 브라우저를 웹 화면으로 조작해 로그인")
    remote.add_argument("--host", default="127.0.0.1", help="바인딩 주소 (기본: 보안 터널용 루프백)")
    remote.add_argument("--port", type=int, default=8765)
    post = sub.add_parser("post", help="게시글 작성")
    post.add_argument("--club-id", type=positive_id, required=True)
    post.add_argument("--menu-id", type=positive_id, required=True)
    post.add_argument("--title", required=True)
    comment = sub.add_parser("comment", help="댓글 작성")
    comment.add_argument("--url", type=article_url, required=True)
    for cmd in (post, comment):
        cmd.add_argument("--body-file", required=True, help="UTF-8 일반 텍스트 파일")
        cmd.add_argument("--submit", action="store_true", help="실제 등록 (생략 시 입력·스크린샷만 수행)")
    return p


def main(argv=None):
    args = parser().parse_args(argv)
    try:
        if args.command == "remote-login":
            from .remote import serve
            if not 1 <= args.port <= 65535:
                raise AutomationError("포트는 1~65535여야 합니다.")
            serve(Path(args.session).absolute(), args.host, args.port)
            return 0
        body = read_text(args.body_file) if args.command != "login" else None
        if args.command == "post" and not args.title.strip():
            raise AutomationError("제목이 비어 있습니다.")
        session = Path(args.session).resolve()
        if args.command != "login" and not session.is_file():
            raise AutomationError("로그인 세션이 없습니다. remote-login 또는 login을 먼저 실행하세요.")
        with sync_playwright() as pw:
            browser = launch_browser(pw, headless=not (args.headed or args.command == "login"))
            try:
                context = browser.new_context(storage_state=str(session) if args.command != "login" else None, locale="ko-KR")
                context.set_default_timeout(20000)
                page = context.new_page()
                if args.command == "login":
                    page.goto("https://nid.naver.com/nidlogin.login", wait_until="domcontentloaded")
                    input("브라우저에서 로그인과 추가 인증을 완료한 뒤 Enter를 누르세요: ")
                    page.goto("https://nid.naver.com/user2/help/myInfo?lang=ko_KR", wait_until="domcontentloaded")
                    if "nidlogin" in page.url or not any(c["name"] == "NID_AUT" for c in context.cookies("https://naver.com")):
                        raise AutomationError("로그인을 확인하지 못했습니다.")
                    save_state(session, context.storage_state())
                    print(f"로그인 세션 저장: {session} (공유하거나 Git에 추가하지 마세요)")
                else:
                    if args.command == "post":
                        prepare_post(page, args.club_id, args.menu_id, args.title, body)
                    else:
                        prepare_comment(page, args.url, body)
                    if args.submit:
                        submit(page, args.command)
                    else:
                        Path("artifacts").mkdir(exist_ok=True, mode=0o700)
                        page.screenshot(path=f"artifacts/{args.command}-preview.png", full_page=True)
                        print(f"입력 완료, 등록하지 않았습니다. 미리보기: artifacts/{args.command}-preview.png")
            finally:
                browser.close()
        return 0
    except (AutomationError, BrowserTimeout, OSError, EOFError) as exc:
        print(f"실행 중단: {exc}", file=sys.stderr)
        return 1
    except Exception as exc:
        # Browser errors can contain page content; avoid dumping session or request details.
        print(f"브라우저 실행 실패 ({type(exc).__name__}). 브라우저 설치·화면 환경·세션을 확인하세요.", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
