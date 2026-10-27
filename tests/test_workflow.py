import argparse
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from playwright.sync_api import sync_playwright
from navercafe_auto.cli import article_url, positive_id, read_text, AutomationError, first_visible, fill_editor, prepare_comment, launch_browser, submit


class ValidationTests(unittest.TestCase):
    def test_reject_untrusted_urls(self):
        for url in ['http://cafe.naver.com/a/1', 'https://cafe.naver.com.evil.test/a/1', 'https://cafe.naver.com/a/1?x=y', 'https://user@cafe.naver.com/a/1']:
            with self.subTest(url=url), self.assertRaises(argparse.ArgumentTypeError):
                article_url(url)
        self.assertEqual(article_url('https://cafe.naver.com/mycafe/123'), 'https://cafe.naver.com/mycafe/123')

    def test_ids_and_empty_body(self):
        for value in ['0', '-1', 'abc', '１２']:
            with self.assertRaises(argparse.ArgumentTypeError):
                positive_id(value)
        with TemporaryDirectory() as directory:
            path = Path(directory) / 'body.txt'
            path.write_text('  ', encoding='utf-8')
            with self.assertRaises(AutomationError):
                read_text(str(path))


class BrowserTests(unittest.TestCase):
    def test_post_editor_and_framed_comment(self):
        with sync_playwright() as pw:
            browser = launch_browser(pw)
            try:
                page = browser.new_page()
                page.set_content('<textarea placeholder="제목을 입력하세요"></textarea><div class="se-component-content"><div contenteditable="true"></div></div>')
                first_visible(page, ['textarea']).fill('테스트 제목')
                fill_editor(page, '첫째 줄\n둘째 줄')
                self.assertEqual(page.locator('textarea').input_value(), '테스트 제목')
                self.assertEqual(page.locator('[contenteditable]').inner_text(), '첫째 줄\n둘째 줄')
                page.route('https://cafe.naver.com/**', lambda route: route.fulfill(content_type='text/html', body='<iframe id="cafe_main" srcdoc="&lt;div class=CommentWriter&gt;&lt;textarea&gt;&lt;/textarea&gt;&lt;/div&gt;"></iframe>'))
                prepare_comment(page, 'https://cafe.naver.com/test/1', '댓글 테스트')
                self.assertEqual(page.frame_locator('#cafe_main').locator('textarea').input_value(), '댓글 테스트')
                # Exercise one real browser POST against a local mocked server response.
                page.route('https://cafe.naver.com/api/articles/1/comments', lambda route: route.fulfill(content_type='application/json', body='{"result":{"commentId":42}}'))
                page.set_content("""<div class="CommentWriter"><button onclick="fetch('https://cafe.naver.com/api/articles/1/comments', {method:'POST'})">등록</button></div>""")
                submit(page, 'comment')
                page.unroute('https://cafe.naver.com/api/articles/1/comments')
                page.route('https://cafe.naver.com/api/articles/1/comments', lambda route: route.fulfill(content_type='application/json', body='{"error":{"code":"NO_PERMISSION"}}'))
                with self.assertRaises(AutomationError):
                    submit(page, 'comment')
            finally:
                browser.close()


if __name__ == '__main__':
    unittest.main()
