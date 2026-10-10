"""Follow the observed Buy Now link; preserve retail observations, not live pipeline success."""
import sys,json,time,re
from pathlib import Path
from bs4 import BeautifulSoup
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from product_tool.adapters.xiaomi import XiaomiAdapter
from product_tool.adapters.published_page import published_links,embedded_objects,records
R=Path(__file__).parent;out=R/'buybox_structure';out.mkdir(exist_ok=True)
prior=json.loads((R/'retail_structure/result.json').read_text(encoding='utf8'))
cap=R/'retail_structure/captures'/prior['captures'][-1]['file'];html=cap.read_text(encoding='utf8')
url=next(u for u,t in published_links(html,prior['final_url']) if t=='Buy Now')
a=XiaomiAdapter(fetch_log_path=out/'fetch_log.json',capture_dir=out/'captures');a.deadline=time.monotonic()+90;a.proofs=[]
p=a.fetch(url,provider='published_buybox_census',source_type='store_buybox')
result={'origin':'separate actual live structural census; never worker-seeded PDP or accepted retail relation','observed_buy_link':url,'page_received':bool(p),'captures':a.proofs,'payload_records':[],'scripts':[]}
if p:
    soup=BeautifulSoup(p[0],'html.parser');result['title']=soup.title.get_text(' ',strip=True) if soup.title else '';result['scripts']=[s['src'] for s in soup.select('script[src]')];result['visible_text_excerpt']=soup.get_text(' ',strip=True)[:2500]
    for obj in embedded_objects(p[0]):
        for d in records(obj):
            keys=[k for k in d if any(x in k.casefold() for x in ('sku','goodsid','productid','commodity','memory','storage','colour','color','variant'))]
            if keys:result['payload_records'].append({k:d[k] for k in keys})
    result['payload_records']=result['payload_records'][:100]
(out/'result.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf8');print('BuyBox received',bool(p),'payload records',len(result['payload_records']));print(result.get('visible_text_excerpt','')[:600])
