"""Offline rendered DOM contract for Bing result cards and DDG challenges."""
from dataclasses import asdict
from pathlib import Path
import unittest

from playwright.sync_api import sync_playwright
from product_tool.census.browser_contracts import BrowserBudget

SCRIPT=Path('product_tool/census/browser_projection.js').read_text(encoding='utf-8')
POLICY={**asdict(BrowserBudget()), 'allowed_hosts':['www.bing.com','www.lg.com'],
        'queries':['ZZ1000'], 'search_result_hosts':['www.lg.com'],
        'render_mode':'render_existing_search_result'}


class ProviderProjectionTests(unittest.TestCase):
    def test_bing_observed_results_include_positionable_url_title_snippet(self):
        html='''<main><ol><li class="b_algo"><h2><a href="https://www.lg.com/uk/appliances/zz1000/">LG ZZ1000</a></h2>
        <div class="b_caption"><p>Official model details and capacity.</p>
        <a href="https://www.lg.com/uk/support/zz1000/">Cached link</a></div></li>
        <li class="b_algo"><h2><a href="https://example.test/other/">Unrelated result</a></h2>
        <div class="b_caption"><p>Another indexed page.</p></div></li></ol></main>'''
        with sync_playwright() as playwright:
            browser=playwright.chromium.launch(headless=True)
            page=browser.new_page()
            page.route('https://www.bing.com/search*',
                       lambda route: route.fulfill(status=200,content_type='text/html',body=html))
            page.goto('https://www.bing.com/search?q=ZZ1000')
            result=page.evaluate(SCRIPT,POLICY)
            browser.close()
        links=[f for f in result['fragments'] if f['type']=='result_link']
        self.assertEqual([f['url'] for f in links],
                         ['https://www.lg.com/uk/appliances/zz1000/',
                          'https://example.test/other/'])
        self.assertEqual(links[0]['title'],'LG ZZ1000')
        self.assertIn('Official model details',links[0]['snippet'])

    def test_ddg_http_202_challenge_is_recognized_from_visible_dom(self):
        html='<main><p>Unfortunately, bots use DuckDuckGo too.</p><p>Please complete the following challenge to confirm this search was made by a human.</p></main>'
        with sync_playwright() as playwright:
            browser=playwright.chromium.launch(headless=True)
            page=browser.new_page()
            page.route('https://duckduckgo.com/*',
                       lambda route: route.fulfill(status=202,content_type='text/html',body=html))
            page.goto('https://duckduckgo.com/?q=ZZ1000')
            result=page.evaluate(SCRIPT,{**POLICY,'allowed_hosts':['duckduckgo.com','www.lg.com']})
            browser.close()
        self.assertTrue(result['protection'])
        self.assertEqual(result['fragments'],[])


if __name__=='__main__':
    unittest.main()
