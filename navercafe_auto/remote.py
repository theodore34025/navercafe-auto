"""Authenticated remote login screen; no password/cookie values are logged."""
from __future__ import annotations

import asyncio
import contextlib
import hashlib
import hmac
import math
import os
import secrets
import shutil
import time
from pathlib import Path
from urllib.parse import urlsplit

from aiohttp import web
from playwright.async_api import async_playwright

from .session import save_state

LOGIN_URL = 'https://nid.naver.com/nidlogin.login'
VERIFY_URL = 'https://nid.naver.com/user2/help/myInfo?lang=ko_KR'
VIEWPORT = {'width': 1280, 'height': 800}
STATIC = Path(__file__).with_name('static')
COOKIE = 'navercafe_remote'


class LoginError(RuntimeError):
    pass


class RemoteBrowser:
    def __init__(self, session_path: Path):
        self.session_path = session_path
        self.pw = self.browser = self.context = self.page = None
        self.saved = False
        self.last_input = time.monotonic()
        self.lock = asyncio.Lock()

    async def start(self):
        await self.close()
        self.pw = await async_playwright().start()
        try:
            executable = os.environ.get('NAVER_BROWSER_EXECUTABLE') or shutil.which('chromium')
            self.browser = await self.pw.chromium.launch(executable_path=executable, headless=True)
            self.context = await self.browser.new_context(viewport=VIEWPORT, locale='ko-KR', accept_downloads=False)
            self.page = await self.context.new_page()
            self.context.on('page', lambda page: asyncio.create_task(page.close()) if page != self.page else None)
            self.page.set_default_timeout(15000)
            # Keep this remote browser on Naver; other hosts can still supply images/scripts.
            await self.context.route('**/*', self._route)
            await self.page.goto(LOGIN_URL, wait_until='domcontentloaded')
            self.saved = False
        except Exception as exc:
            await self.close()
            if 'ERR_CERT_AUTHORITY_INVALID' in str(exc):
                raise LoginError('Chromium이 클라우드 프록시 인증서를 신뢰하지 않습니다. 환경의 CA 신뢰 설정 승인이 필요합니다.') from None
            raise LoginError('네이버 로그인 화면을 열지 못했습니다. 네트워크 허용 설정을 확인하세요.') from None

    async def _route(self, route):
        request = route.request
        if request.is_navigation_request():
            url = urlsplit(request.url)
            if url.scheme != 'https' or not (url.hostname or '').endswith('.naver.com'):
                await route.abort()
                return
        await route.continue_()

    async def close(self):
        try:
            if self.browser:
                await self.browser.close()
        finally:
            self.browser = self.context = self.page = None
            if self.pw:
                await self.pw.stop()
                self.pw = None

    def require_page(self):
        if self.page is None or self.page.is_closed():
            raise LoginError('먼저 로그인 화면 열기를 누르세요.')

    async def save(self):
        self.require_page()
        # Cookie presence alone is insufficient: check an authenticated page too.
        response = await self.page.goto(VERIFY_URL, wait_until='domcontentloaded')
        cookies = await self.context.cookies('https://naver.com')
        target = urlsplit(self.page.url)
        if (response is None or not response.ok or target.hostname != 'nid.naver.com'
                or not target.path.startswith('/user2/')
                or not any(c['name'] == 'NID_AUT' and c['value'] for c in cookies)):
            raise LoginError('로그인을 확인하지 못했습니다. 로그인과 추가 인증을 완료하세요.')
        save_state(self.session_path, await self.context.storage_state())
        self.saved = True

    async def action(self, data):
        self.last_input = time.monotonic()
        kind = data.get('type')
        if kind == 'start':
            await self.start()
            return '로그인 화면을 열었습니다. 화면에서 직접 로그인하세요.'
        if kind == 'close':
            await self.close()
            return '원격 브라우저를 종료했습니다. 저장한 세션 파일은 유지됩니다.'
        self.require_page()
        if kind == 'save':
            await self.save()
            return '로그인 세션을 저장했습니다. 게시글·댓글 명령에서 사용할 수 있습니다.'
        if kind == 'text':
            text = data.get('text')
            if not isinstance(text, str) or not 0 < len(text) <= 10000:
                raise LoginError('입력할 텍스트는 1~10000자여야 합니다.')
            await self.page.keyboard.insert_text(text)
        elif kind == 'key':
            key = data.get('key')
            if not isinstance(key, str) or not 0 < len(key) <= 80:
                raise LoginError('올바르지 않은 키 입력입니다.')
            await self.page.keyboard.press(key)
        elif kind == 'mouse':
            x, y = data.get('x'), data.get('y')
            if not all(isinstance(v, (float, int)) and math.isfinite(v) for v in (x, y)) or not (0 <= x < 1280 and 0 <= y < 800):
                raise LoginError('화면 안의 위치를 선택하세요.')
            operation = data.get('operation')
            if operation not in ('down', 'up', 'move'):
                raise LoginError('올바르지 않은 마우스 입력입니다.')
            await self.page.mouse.move(x, y)
            if operation == 'down':
                await self.page.mouse.down()
            elif operation == 'up':
                await self.page.mouse.up()
        elif kind == 'wheel':
            delta = data.get('delta')
            if not isinstance(delta, (float, int)) or not math.isfinite(delta):
                raise LoginError('올바르지 않은 스크롤 입력입니다.')
            await self.page.mouse.wheel(0, max(-1000, min(1000, delta)))
        else:
            raise LoginError('지원하지 않는 동작입니다.')
        return None


def access_token(path: Path) -> str:
    # A fresh token per server run; no credentials in URLs, logs, or git.
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    token = secrets.token_urlsafe(32)
    save_state(path, {'token': token})
    return token


def same_origin(request):
    origin = urlsplit(request.headers.get('Origin', ''))
    return origin.scheme in ('http', 'https') and origin.netloc == request.host


def create_app(session_path: Path, token: str, *, remote=None):
    remote = remote or RemoteBrowser(session_path)
    cookie_value = hmac.new(token.encode(), secrets.token_bytes(32), hashlib.sha256).hexdigest()
    authenticated_until = 0.0

    def authorized(request):
        return time.monotonic() < authenticated_until and hmac.compare_digest(request.cookies.get(COOKIE, '').encode(), cookie_value.encode())

    @web.middleware
    async def security(request, handler):
        if request.path in ('/action', '/screen', '/status') and not authorized(request):
            return web.Response(status=401, text='접속 코드를 입력하세요.', headers={'Cache-Control':'no-store'})
        if request.method == 'POST' and not same_origin(request):
            return web.Response(status=403, text='같은 화면에서 요청하세요.', headers={'Cache-Control':'no-store'})
        try:
            response = await handler(request)
        except web.HTTPException as exc:
            response = web.Response(status=exc.status, text=exc.text, headers=exc.headers)
        response.headers.update({
            'Cache-Control': 'no-store',
            'X-Content-Type-Options': 'nosniff',
            'Referrer-Policy': 'no-referrer',
            'X-Frame-Options': 'DENY',
            'Content-Security-Policy': "default-src 'self'; img-src 'self' blob:; script-src 'self'; style-src 'self'; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'",
        })
        return response

    async def home(request):
        return web.FileResponse(STATIC / 'remote.html')

    async def asset(request):
        return web.FileResponse(STATIC / request.match_info['file'])

    async def auth(request):
        nonlocal authenticated_until
        form = await request.post()
        candidate = form.get('token', '')
        if not isinstance(candidate, str) or not hmac.compare_digest(candidate.encode(), token.encode()):
            return web.json_response({'message': '접속 코드가 올바르지 않습니다.'}, status=401)
        authenticated_until = time.monotonic() + 1800
        response = web.json_response({'message': '접속되었습니다.'})
        # HTTPS reverse proxies must preserve Host and set X-Forwarded-Proto.
        secure = request.secure or request.headers.get('X-Forwarded-Proto') == 'https'
        response.set_cookie(COOKIE, cookie_value, httponly=True, samesite='Strict', secure=secure, max_age=1800)
        return response

    async def status(request):
        return web.json_response({'running': remote.page is not None, 'saved': remote.saved})

    async def screen(request):
        async with remote.lock:
            if remote.page is None or remote.page.is_closed():
                return web.Response(status=409, text='로그인 화면을 먼저 열어주세요.')
            try:
                picture = await remote.page.screenshot(type='jpeg', quality=75, timeout=5000)
            except Exception:
                return web.Response(status=503, text='화면을 갱신하는 중입니다.')
        return web.Response(body=picture, content_type='image/jpeg')

    async def action(request):
        try:
            data = await request.json()
            if not isinstance(data, dict):
                raise LoginError('올바르지 않은 요청입니다.')
            async with remote.lock:
                message = await remote.action(data)
            return web.json_response({'message': message})
        except LoginError as exc:
            return web.json_response({'message': str(exc)}, status=400)
        except (ValueError, TypeError):
            return web.json_response({'message': '요청 형식이 올바르지 않습니다.'}, status=400)
        except Exception:
            return web.json_response({'message': '브라우저 동작에 실패했습니다. 화면 상태를 확인하세요.'}, status=400)

    async def reap_idle():
        while True:
            await asyncio.sleep(30)
            if time.monotonic() - remote.last_input > 900:
                async with remote.lock:
                    await remote.close()

    async def lifecycle(app):
        task = asyncio.create_task(reap_idle())
        yield
        task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await task
        await remote.close()

    app = web.Application(middlewares=[security], client_max_size=32768)
    app.cleanup_ctx.append(lifecycle)
    app.router.add_get('/', home)
    app.router.add_get('/static/{file:remote\\.(?:js|css)}', asset)
    app.router.add_post('/auth', auth)
    app.router.add_get('/status', status)
    app.router.add_get('/screen', screen)
    app.router.add_post('/action', action)
    return app


def serve(session_path: Path, host: str, port: int):
    token_path = Path('.remote-login/access.json').resolve()
    token = access_token(token_path)
    print(f'원격 로그인 서버 포트: {port}')
    print(f'접속 코드는 {token_path}의 token 항목에 있습니다. 본인 터미널에서만 확인하세요.')
    print('사용자 접속에는 보안 포트 전달 또는 HTTPS 경로가 필요합니다. 브라우저 입력은 기록하지 않습니다.')
    web.run_app(create_app(session_path, token), host=host, port=port, access_log=None, print=None)
