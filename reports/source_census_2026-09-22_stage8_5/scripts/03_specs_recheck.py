import sys, json, re
sys.path.insert(0, r'C:\Users\Julynce\AppData\Local\Temp\claude\a--work-dev-product-cards-mvp\9962257a-7031-4112-8b5f-503975d81cc3\scratchpad\stage85')
from lib import fetch, save_fixture, OUT, budget_status
from bs4 import BeautifulSoup

hosts = ('www.samsung.com',)
url = 'https://www.samsung.com/kz_ru/microwave-ovens/solo/ms23k3614akbw/'
page, err = fetch(url, hosts, 'product', reason='re-fetch of the SAME already-confirmed product page (Stage 8.4) with a broader specification text search -- Stage 8.4 only regex-matched a narrow keyword set (volume/power/grill/convection) and may have missed other characteristic rows; this closes the specific unclosed field "which characteristics remain unknown"')
result = {'url': url, 'error': err}
if page:
    text = page['raw_text']
    soup = BeautifulSoup(text, 'html.parser')
    fx = save_fixture(page['struct'])
    result['fixture'] = fx
    body_text = soup.get_text('\n', strip=True)
    # broad label: value scan -- look for any short "Label\nValue"-shaped pairs near known spec keywords
    broad_keywords = ['вес', 'масса', 'высота', 'ширина', 'глубина', 'размер', 'габарит', 'управлен',
                       'тарелк', 'диаметр', 'программ', 'разморозк', 'таймер', 'дисплей', 'защит', 'гарантия',
                       'мощност', 'объем', 'вольт', 'частот', 'шум', 'звук']
    hits = []
    for kw in broad_keywords:
        for m in re.finditer(r'.{0,15}' + kw + r'\w*.{0,40}', body_text, re.I):
            hits.append(m.group(0).replace('\n', ' | '))
    # dedupe, preserve order
    seen = set()
    dedup_hits = []
    for h in hits:
        if h not in seen:
            seen.add(h)
            dedup_hits.append(h)
    result['broad_spec_hits'] = dedup_hits[:60]
    print('total broad hits (deduped):', len(dedup_hits))
    for h in dedup_hits[:60]:
        print(' ', h)
else:
    print('FAILED', err)

json.dump(result, open(OUT / 'specs_recheck.json', 'w', encoding='utf-8'), indent=2, ensure_ascii=False)
print('budget after:', budget_status())
