import asyncio
import json
import stat
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from aiohttp import CookieJar
from aiohttp.test_utils import TestClient, TestServer
from playwright.async_api import async_playwright, expect

from navercafe_auto.remote import RemoteBrowser, create_app


class MockNaver(RemoteBrowser):
    """Serve synthetic login pages through the real remote Chromium context."""
    async def _route(self, route):
        if '/nidlogin.login' in route.request.url:
            await route.fulfill(content_type='text/html', body='''<!doctype html><html><meta charset="utf-8"><body>
                <label>ID<input id="id"></label><label>Password<input id="password" type="password"></label>
                <button id="login" onclick="document.cookie='NID_AUT=synthetic-test-cookie;path=/;domain=.naver.com;Secure';location.href='/user2/help/myInfo?lang=ko_KR'">로그인</button>
                </body></html>''')
        else:
            await route.fulfill(content_type='text/html', body='<html><body>Account information</body></html>')


class RemoteLoginTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.temp = TemporaryDirectory()
        self.state = Path(self.temp.name) / 'state.json'
        self.remote = MockNaver(self.state)
        self.client = TestClient(TestServer(create_app(self.state, 'test-only-access-code', remote=self.remote)), cookie_jar=CookieJar(unsafe=True))
        await self.client.start_server()
        self.origin = str(self.client.make_url('/')).rstrip('/')

    async def asyncTearDown(self):
        await self.client.close()
        self.temp.cleanup()

    async def auth(self):
        response = await self.client.post('/auth', data={'token': 'test-only-access-code'}, headers={'Origin': self.origin})
        self.assertEqual(response.status, 200)

    async def command(self, data):
        return await self.client.post('/action', json=data, headers={'Origin': self.origin})

    async def test_authentication_origin_and_private_screen(self):
        self.assertEqual((await self.client.get('/screen')).status, 401)
        self.assertEqual((await self.client.post('/auth', data={'token':'wrong'}, headers={'Origin': self.origin})).status, 401)
        self.assertEqual((await self.client.post('/auth', data={'token':'test-only-access-code'}, headers={'Origin':'https://other.example'})).status, 403)
        await self.auth()
        self.assertEqual((await self.client.get('/screen')).status, 409)
        self.assertEqual((await self.client.post('/action', json={'type':'start'}, headers={'Origin':'https://other.example'})).status, 403)
        response = await self.command({'type':'start'})
        self.assertEqual(response.status, 200, await response.text())
        screen = await self.client.get('/screen')
        self.assertEqual(screen.content_type, 'image/jpeg')
        self.assertEqual(screen.headers['Cache-Control'], 'no-store')
        self.assertTrue((await screen.read()).startswith(b'\xff\xd8'))
        self.assertEqual((await self.command({'type':'save'})).status, 400)
        self.assertFalse(self.state.exists(), 'Failed authentication must not create a session')
        self.assertEqual((await self.command({'type':'mouse','x':-1,'y':0,'operation':'down'})).status, 400)
        self.assertEqual((await self.command({'type':'close'})).status, 200)
        self.assertEqual((await self.client.get('/screen')).status, 409)

    async def test_web_ui_input_save_and_cli_session_reuse(self):
        async with async_playwright() as pw:
            # The user-facing browser is distinct from the server's Naver browser.
            import shutil
            browser = await pw.chromium.launch(executable_path=shutil.which('chromium'))
            try:
                page = await browser.new_page()
                await page.goto(self.origin)
                await page.locator('#token').fill('test-only-access-code')
                await page.locator('#auth-form button').click()
                await page.locator('#control-panel').wait_for(state='visible')
                await page.locator('#start').click()
                await page.locator('#screen').wait_for(state='visible')
                await self.remote.page.locator('#id').wait_for()

                async def click_remote(selector):
                    remote_box = await self.remote.page.locator(selector).bounding_box()
                    image_box = await page.locator('#screen').bounding_box()
                    await page.locator('#screen').click(position={
                        'x': (remote_box['x'] + remote_box['width']/2) * image_box['width']/1280,
                        'y': (remote_box['y'] + remote_box['height']/2) * image_box['height']/800,
                    })

                await click_remote('#id')
                await page.keyboard.type('example-user')
                await self.remote.page.wait_for_function("document.querySelector('#id').value === 'example-user'")
                await click_remote('#password')
                await page.locator('#text').fill('synthetic password 한글')
                await page.locator('#text-form button').click()
                await self.remote.page.wait_for_function("document.querySelector('#password').value === 'synthetic password 한글'")
                self.assertEqual(await page.locator('#text').input_value(), '')
                await click_remote('#login')
                await self.remote.page.wait_for_url('**/user2/**')
                await page.locator('#save').click()
                await expect(page.locator('#status')).to_contain_text('세션을 저장했습니다')
                self.assertTrue(self.state.exists())
                self.assertEqual(stat.S_IMODE(self.state.stat().st_mode), 0o600)
                state = json.loads(self.state.read_text())
                self.assertTrue(any(c['name'] == 'NID_AUT' for c in state['cookies']))
                # Existing CLI uses this exact storage_state format.
                context = await browser.new_context(storage_state=str(self.state))
                self.assertTrue(any(c['name'] == 'NID_AUT' for c in await context.cookies('https://naver.com')))
                await context.close()
                await page.locator('#close').click()
                await expect(page.locator('#status')).to_contain_text('종료했습니다')
                self.assertIsNone(self.remote.browser)
            finally:
                await browser.close()


if __name__ == '__main__':
    unittest.main()
