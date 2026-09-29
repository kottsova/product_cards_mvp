import sys, json, re
sys.path.insert(0, r'C:\Users\Julynce\AppData\Local\Temp\claude\a--work-dev-product-cards-mvp\9962257a-7031-4112-8b5f-503975d81cc3\scratchpad\stage85')
from lib import fetch_binary, OUT, budget_status

hosts = {'org.downloadcenter.samsung.com', 'downloadcenter.samsung.com'}
url = 'https://org.downloadcenter.samsung.com/downloadfile/ContentsFile.aspx?CDSite=UNI_KZ_RU&OriginYN=N&ModelType=N&ModelName=MS23K3614AK&CttFileID=7400287&CDCttType=UM&VPath=UM%2F201907%2F20190723164117830%2FMS23K3614AK_BW_DE68-04547Q-00_RU-UK-KK-UZ.pdf'

result, err = fetch_binary(url, hosts, reason='binary-safe fetch of the manual PDF to extract real text/metadata -- Stage 8.4 only confirmed magic bytes via the lossy text-decoding probe.probe() path and did not persist bytes; this stage needs the actual content, not just reachability')
out = {'url': url, 'error': err}
if result:
    data = result['bytes']
    out['final_url'] = result['final_url']
    out['content_type'] = result['content_type']
    out['bytes_read'] = result['bytes_read']
    out['truncated'] = result['truncated']
    # Save to the SESSION SCRATCHPAD only (outside the git repo), never into reports/.
    scratch_pdf = Path = __import__('pathlib').Path(r'C:\Users\Julynce\AppData\Local\Temp\claude\a--work-dev-product-cards-mvp\9962257a-7031-4112-8b5f-503975d81cc3\scratchpad\stage85\manual.pdf')
    scratch_pdf.write_bytes(data)
    out['scratch_path'] = str(scratch_pdf)
    print('bytes_read', result['bytes_read'], 'truncated', result['truncated'], 'content_type', result['content_type'])
else:
    print('FAILED', err)

json.dump(out, open(OUT / 'pdf_fetch_meta.json', 'w', encoding='utf-8'), indent=2, ensure_ascii=False)
print('budget after:', budget_status())
