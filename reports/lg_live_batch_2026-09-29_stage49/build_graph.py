from __future__ import annotations
from pathlib import Path
import json,hashlib,sqlite3
from bs4 import BeautifulSoup
from product_tool.fetch_history import latest_source_snapshot
from product_tool.lg_identity import article_has_variant, product_edges, support_edges
DB=Path('data/batches.sqlite3');OUT=Path('reports/lg_live_batch_2026-09-29_stage49/identity_graph.json')
c=sqlite3.connect(DB);c.row_factory=sqlite3.Row
batch='ae3d2cb381744ba8a811e54231233254'
rows=[]
for p in c.execute('select id,search_code from products where batch_id=? order by id',(batch,)):
 item={'id':p['id'],'article':p['search_code'],'product_sources':[]}
 for key,region in (('lg_kz','kz'),('lg_ru','ru')):
  page=c.execute('select * from source_pages where product_id=? and source_key=?',(p['id'],key)).fetchone()
  if not page:continue
  snap=latest_source_snapshot(DB,p['id'],key)
  codes=[];edges=[]
  if snap and snap['content'] and snap['source_url']==page['url']:
   assert hashlib.sha256(snap['content'].encode()).hexdigest()==snap['content_sha256']
   soup=BeautifulSoup(snap['content'],'html.parser')
   if region=='kz':
    for node in soup.select('.price-area__PD0033[data-analytics]'):
     try:code=json.loads(node['data-analytics']).get('data-pim-sku','')
     except ValueError:code=''
     if code:codes.append(code)
   else:
    for node in soup.select('.GPC0009[data-adobe-salesmodelcode]'):
     model=node.get('data-adobe-salesmodelcode','');suffix=node.get('data-adobe-salessuffixcode','')
     if model and suffix:codes.append(model+'.'+suffix)
   codes=list(dict.fromkeys(codes))
   edges=[x.as_dict() for x in product_edges(key,page['url'],p['search_code'],codes)]
  item['product_sources'].append({'source':key,'url':page['url'],'stored_level':page['match_level'],
        'main_pdp_codes':codes,'edges':edges,'snapshot_id':snap['id'] if snap else None})
 item['catalog_has_variant']=article_has_variant(p['search_code'],(x for source in item['product_sources'] for x in source['main_pdp_codes']))
 rows.append(item)
api=c.execute('select * from source_snapshots where id=127').fetchone(); assert hashlib.sha256(api['content'].encode()).hexdigest()==api['content_sha256']
obj=json.loads(api['content'])['productSupportPage'];manual=obj['manualSoftwareList'];codes=[manual['csSalesCode'],manual['modelList']['csSalesCode']]
kit={'support_url':'https://www.lg.com/kz/support/product-support/cs-P12ED.USAR/',
     'api_url':api['source_url'],'api_snapshot_id':127,'api_sha256':api['content_sha256'],
     'code_paths':{'productSupportPage.manualSoftwareList.csSalesCode':manual['csSalesCode'],
                   'productSupportPage.manualSoftwareList.modelList.csSalesCode':manual['modelList']['csSalesCode']},
     'edges':[e.as_dict() for e in support_edges('lg_kz_support','https://www.lg.com/kz/support/product-support/cs-P12ED.USAR/','P12ED.NSAR + P12ED.USAR',codes)],
     'russian_manual_api_item':next((x for x in manual['manualList']['manualList'] if x.get('fileNamePrint')=='Russian'),None)}
OUT.write_text(json.dumps({'batch_id':batch,'rows':rows,'p12ed_support':kit},ensure_ascii=False,indent=2),encoding='utf8')
print('rows',len(rows),'support_edges',len(kit['edges']))
for x in rows:
 print(x['article'],x['catalog_has_variant'],[(s['source'],s['stored_level'],s['main_pdp_codes'][:1],[e['relation'] for e in s['edges']][:1]) for s in x['product_sources']])
