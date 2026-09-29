import sys, json
sys.path.insert(0, r'C:\Users\Julynce\AppData\Local\Temp\claude\a--work-dev-product-cards-mvp\9962257a-7031-4112-8b5f-503975d81cc3\scratchpad\stage84')
from lib import fetch, OUT, budget_status

# First attempt (already logged in run_state.json) rejected the response as a
# REGIONAL_REDIRECT because the redirect target host (downloadcenter.samsung.com,
# WITHOUT the 'org.' prefix) was not in the originally-declared allowed_hosts.
# Both hostnames are directly observed, first-party samsung.com infrastructure
# (the redirect target came from the prior fetch's own redirect_chain, not invented),
# so this retry widens allowed_hosts to include exactly that already-observed target.
hosts = ('org.downloadcenter.samsung.com', 'downloadcenter.samsung.com')
url = 'https://org.downloadcenter.samsung.com/downloadfile/ContentsFile.aspx?CDSite=UNI_KZ_RU&OriginYN=N&ModelType=N&ModelName=MS23K3614AK&CttFileID=7400287&CDCttType=UM&VPath=UM%2F201907%2F20190723164117830%2FMS23K3614AK_BW_DE68-04547Q-00_RU-UK-KK-UZ.pdf'
page, err = fetch(url, hosts, 'document',
                   reason='retry of the manual reachability check with the already-OBSERVED redirect target host (downloadcenter.samsung.com, seen in the prior attempts own redirect_chain) added to allowed_hosts -- not a new/invented domain')
result = {'url': url, 'error': err}
if page:
    result['http_status'] = page['http_status']
    result['final_url'] = page['final_url']
    result['redirect_chain'] = page['redirect_chain']
    text = page['raw_text']
    result['content_len'] = len(text)
    result['looks_like_pdf_magic_bytes'] = text[:8].startswith('%PDF') if text else False
    print('http_status', page['http_status'], 'final_url', page['final_url'])
    print('content_len', len(text), 'looks_like_pdf', result['looks_like_pdf_magic_bytes'])
    print('first 20 chars repr:', repr(text[:20]))
else:
    print('FAILED', err)
json.dump(result, open(OUT / 'manual_reachability_retry.json', 'w', encoding='utf-8'), indent=2, ensure_ascii=False)
print('budget after:', budget_status())
