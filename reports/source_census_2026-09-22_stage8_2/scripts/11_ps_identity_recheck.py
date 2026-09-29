import sys, json
sys.path.insert(0, r'C:\Users\Julynce\AppData\Local\Temp\claude\a--work-dev-product-cards-mvp\9962257a-7031-4112-8b5f-503975d81cc3\scratchpad\stage82')
from lib import fetch, save_fixture, OUT

hosts = ('playstation.com',)
url = 'https://direct.playstation.com/en-us/buy-accessories/dualsense-wireless-controller-cosmic-red-for-ps5-pc-mac-mobile'
terms = ['DualSense', 'Cosmic Red', 'PS5', 'CFI-ZCT1J']
page, err = fetch(url, hosts, 'product', identity_terms=terms)
result = {'url': url, 'error': err}
if page:
    result['identity_term_matches'] = page['identity_term_matches']
    print(json.dumps(page['identity_term_matches'], indent=2, ensure_ascii=False))
json.dump(result, open(OUT / 'ps_controller_identity_check.json', 'w', encoding='utf-8'), indent=2, ensure_ascii=False)
