"""Separate structural research of regional storefront payloads; never a worker PDP seed."""
import sys,json,time,hashlib
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from product_tool.adapters.xiaomi import XiaomiAdapter
from product_tool.adapters.published_page import published_links,embedded_objects,records
R=Path(__file__).parent/'retail_structure';R.mkdir(exist_ok=True)
a=XiaomiAdapter(fetch_log_path=R/'fetch_log.json',capture_dir=R/'captures');a.deadline=time.monotonic()+90;a.proofs=[]
home=a.fetch('https://www.mi.com/uk/',provider='structure_census',source_type='catalog')
assert home
catalog=next(u for u,t in published_links(*home) if '/uk/sitemap/' in u)
body=a.fetch(catalog,provider='structure_census',source_type='html_sitemap');assert body
url=next(u for u,t in published_links(*body) if t=='Xiaomi 15' and '/product/' in u)
p=a.fetch(url,provider='structure_census',source_type='storefront');assert p
result={'origin':'separate actual live structure census; not a discovery seed','published_catalog':catalog,'candidate_url':url,'final_url':p[1],'captures':a.proofs,'identity_records':[],'published_script_urls':[]}
from bs4 import BeautifulSoup
s=BeautifulSoup(p[0],'html.parser');result['published_script_urls']=[x['src'] for x in s.select('script[src]')][:40]
for obj in embedded_objects(p[0]):
    for d in records(obj):
        keys=[k for k in d if any(t in k.casefold() for t in ['skuid','goodsid','productid','variant','memory','storage','colour','color','commodity'])]
        if keys:result['identity_records'].append({k:d[k] for k in keys if isinstance(d[k],(str,int,float,bool,list,dict))})
result['identity_records']=result['identity_records'][:100]
(R/'result.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf8');print('Regional storefront',p[1],'identity payload records',len(result['identity_records']))
