"""Read published regional scripts; no executable JS or guessed API/PDP routes."""
import sys,json,time,re
from pathlib import Path
from urllib.parse import urljoin
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from product_tool.adapters.xiaomi import XiaomiAdapter
R=Path(__file__).parent;out=R/'script_structure';out.mkdir(exist_ok=True)
prior=json.loads((R/'retail_structure/result.json').read_text(encoding='utf8'))
a=XiaomiAdapter(fetch_log_path=out/'fetch_log.json',capture_dir=out/'captures');a.deadline=time.monotonic()+90;a.proofs=[]
found=[]
for u in prior['published_script_urls']:
    if not any(x in u for x in ('uk.config.js','/xiaomi-15/js/main.js','/xiaomi-15/js/public.chunk.js')):continue
    url=urljoin(prior['final_url'],u);p=a.fetch(url,provider='structure_script_census',source_type='published_js')
    if not p:continue
    text=p[0];matches=[]
    for m in re.finditer(r'(?i)skuId|goodsId|productId|commodityId|buybox|/api/|getProduct|/shop/|/buy/|variant|storage|memory',text):
        matches.append(text[max(0,m.start()-100):m.end()+150])
        if len(matches)>=35:break
    endpoints=sorted(set(re.findall(r'''https?://[^\s"'<>\\)]+''',text)))
    found.append({'url':url,'identity_api_contexts':matches,'published_absolute_urls':endpoints[:100],'observation':'actual_live_public_script_text; not evaluated'})
(out/'result.json').write_text(json.dumps({'origin':'actual live inspection of published scripts; not an API success or retail relation','scripts':found,'captures':a.proofs,'limit':'No bound BuyBox/XHR variant payload observed in this bounded census; requires attended storefront network inspection.'},ensure_ascii=False,indent=2),encoding='utf8')
print([(x['url'],len(x['identity_api_contexts'])) for x in found])
