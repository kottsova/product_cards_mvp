import sys, json
sys.path.insert(0, r'C:\Users\Julynce\AppData\Local\Temp\claude\a--work-dev-product-cards-mvp\9962257a-7031-4112-8b5f-503975d81cc3\scratchpad\stage84')
from lib import fetch, OUT, budget_status

hosts = ('org.downloadcenter.samsung.com',)
url = 'https://org.downloadcenter.samsung.com/downloadfile/ContentsFile.aspx?CDSite=UNI_KZ_RU&OriginYN=N&ModelType=N&ModelName=MS23K3614AK&CttFileID=7400287&CDCttType=UM&VPath=UM%2F201907%2F20190723164117830%2FMS23K3614AK_BW_DE68-04547Q-00_RU-UK-KK-UZ.pdf'
page, err = fetch(url, hosts, 'document',
                   reason='reachability/metadata check only (no content parsing) for the user-manual link found directly on the already-fetched MS23K3614AK/BW product page -- first-party Samsung download center domain, model name embedded in the URLs own ModelName= query parameter')
result = {'url': url, 'error': err}
if page:
    result['http_status'] = page['http_status']
    result['final_url'] = page['final_url']
    result['redirect_chain'] = page['redirect_chain']
    result['content_len_bytes_read'] = page['raw_len']
    # sniff for PDF magic bytes / content type hints without persisting the body
    head = page['raw_text'][:8]
    result['looks_like_pdf_magic_bytes'] = head.startswith('%PDF') if isinstance(head, str) else None
    print('http_status', page['http_status'], 'final_url', page['final_url'])
    print('looks_like_pdf_magic_bytes', result['looks_like_pdf_magic_bytes'])
else:
    print('FAILED', err)
json.dump(result, open(OUT / 'manual_reachability_check.json', 'w', encoding='utf-8'), indent=2, ensure_ascii=False)
print('budget after:', budget_status())
