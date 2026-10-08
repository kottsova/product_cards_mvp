"""Observed provider destinations survive redaction, unsafe targets don't."""
import base64,json,unittest
from pathlib import Path
from playwright.sync_api import sync_playwright

class ProviderProjection(unittest.TestCase):
    def test_bing_redirect_is_decoded_before_query_redaction(self):
        script=(Path(__file__).resolve().parents[1]/'product_tool/census/browser_projection.js').read_text(encoding='utf-8')
        target='https://direct.playstation.com/en-gb/buy-consoles/unseen-product?tracking=discard'
        encoded='a1'+base64.urlsafe_b64encode(target.encode()).decode().rstrip('=')
        bad='a1'+base64.urlsafe_b64encode(b'https://user:password@direct.playstation.com/en-gb/buy-consoles/unseen-product').decode().rstrip('=')
        html=f'<main><ol><li class="b_algo"><h2><a href="https://www.bing.com/ck/a?u={encoded}&amp;ntb=1">PlayStation unseen product</a></h2></li><li class="b_algo"><h2><a href="https://www.bing.com/ck/a?u={bad}">Unsafe PS5 result</a></h2></li></ol></main>'
        with sync_playwright() as pw:
            browser=pw.chromium.launch(headless=True);page=browser.new_page()
            page.route('**/*',lambda r:r.fulfill(status=200,body=html,content_type='text/html'))
            page.goto('https://www.bing.com/search?q=PS5',wait_until='domcontentloaded')
            result=page.evaluate(script,dict(allowed_hosts=['www.bing.com','direct.playstation.com'],queries=['PS5'],search_result_hosts=['direct.playstation.com'],render_mode='render_existing_search_result',max_fragment_bytes=10000,max_projection_fragments=100,max_projection_bytes=100000,max_dom_elements=10000))
            browser.close()
        links=[f['url'] for f in result['fragments'] if f['type']=='result_link']
        self.assertEqual(links,['https://direct.playstation.com/en-gb/buy-consoles/unseen-product'])

if __name__=='__main__':unittest.main()
