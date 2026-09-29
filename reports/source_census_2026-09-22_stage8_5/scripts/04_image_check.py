import sys, json
sys.path.insert(0, r'C:\Users\Julynce\AppData\Local\Temp\claude\a--work-dev-product-cards-mvp\9962257a-7031-4112-8b5f-503975d81cc3\scratchpad\stage85')
from lib import fetch_binary, OUT, budget_status

hosts = {'images.samsung.com'}
url = 'https://images.samsung.com/is/image/samsung/kz-ru-ms23k3614akbw-ms23k3614ak-bw-frontblack-190178091?$1164_776_PNG$'
result, err = fetch_binary(url, hosts, reason='verify the card-selected official image actually resolves and is real image content (not a broken/placeholder link) -- closes the specific "is the image fit for the card" check')
out = {'url': url, 'error': err}
if result:
    data = result['bytes']
    out['final_url'] = result['final_url']
    out['content_type'] = result['content_type']
    out['bytes_read'] = result['bytes_read']
    out['truncated'] = result['truncated']
    out['magic_bytes_hex'] = data[:8].hex()
    # PNG magic: 89 50 4E 47 0D 0A 1A 0A ; JPEG: FF D8 FF
    is_png = data[:8] == b'\x89PNG\r\n\x1a\n'
    is_jpeg = data[:3] == b'\xff\xd8\xff'
    out['looks_like_png'] = is_png
    out['looks_like_jpeg'] = is_jpeg
    print('content_type', result['content_type'], 'bytes_read', result['bytes_read'])
    print('looks_like_png', is_png, 'looks_like_jpeg', is_jpeg, 'magic_hex', data[:8].hex())
else:
    print('FAILED', err)
json.dump(out, open(OUT / 'image_check.json', 'w', encoding='utf-8'), indent=2, ensure_ascii=False)
print('budget after:', budget_status())
