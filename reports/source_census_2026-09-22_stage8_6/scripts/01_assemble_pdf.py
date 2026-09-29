import sys, json
sys.path.insert(0, r'C:\Users\Julynce\AppData\Local\Temp\claude\a--work-dev-product-cards-mvp\9962257a-7031-4112-8b5f-503975d81cc3\scratchpad\stage86')
from lib import fetch_document_bounded, OUT, budget_status, ALLOWED_STAGE_HOSTS

url = 'https://org.downloadcenter.samsung.com/downloadfile/ContentsFile.aspx?CDSite=UNI_KZ_RU&OriginYN=N&ModelType=N&ModelName=MS23K3614AK&CttFileID=7400287&CDCttType=UM&VPath=UM%2F201907%2F20190723164117830%2FMS23K3614AK_BW_DE68-04547Q-00_RU-UK-KK-UZ.pdf'

result = fetch_document_bounded(url, ALLOWED_STAGE_HOSTS,
                                 reason='bounded Range-aware assembly of the already-known manual PDF -- control document for the new reusable large-document capability')

summary = {
    'url': url,
    'completeness': result['completeness'],
    'reason': result['reason'],
    'declared_total_bytes': result.get('declared_total_bytes'),
    'bytes_assembled': result.get('bytes_assembled') or (len(result['bytes']) if result.get('bytes') else None),
    'log': result['log'],
}
print(json.dumps(summary, indent=2, ensure_ascii=False))

if result.get('bytes'):
    scratch_pdf = __import__('pathlib').Path(r'C:\Users\Julynce\AppData\Local\Temp\claude\a--work-dev-product-cards-mvp\9962257a-7031-4112-8b5f-503975d81cc3\scratchpad\stage86\manual_full.pdf')
    scratch_pdf.write_bytes(result['bytes'])
    summary['scratch_path'] = str(scratch_pdf)
    print('saved to scratch:', scratch_pdf, 'size:', len(result['bytes']))

json.dump(summary, open(OUT / 'assembly_result.json', 'w', encoding='utf-8'), indent=2, ensure_ascii=False)
print('budget after:', budget_status())
