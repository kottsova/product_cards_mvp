from pathlib import Path
from bs4 import BeautifulSoup
from product_tool.fetch_history import latest_source_snapshot
from product_tool.adapters.samsung import _json_ld_product,page_model_data,extract_spec_table,extract_document_links,extract_photos
p=Path('reports/samsung_stage59/baseline.sqlite3')
snap=latest_source_snapshot(p,1,'samsung')
html=snap['content']; url=snap['source_url']; soup=BeautifulSoup(html,'html.parser')
product=_json_ld_product(soup)
print('bytes',len(html),'canonical',[x.get('href') for x in soup.select('link[rel="canonical"]')])
print('alternates',[(x.get('hreflang'),x.get('href')) for x in soup.select('link[rel="alternate"][hreflang]')][:12])
print('jsonld_product',{k:product.get(k) for k in ('@type','sku','name','image','url') if k in product})
print('page_model_data',page_model_data(html))
print('support_links',sorted({x.get('href') for x in soup.select('a[href]') if '/support/model/' in x.get('href','')})[:15])
print('spec_groups',sorted({x.group for x in extract_spec_table(html)}))
print('spec_count',len(extract_spec_table(html)))
print('document_links',[(x.file_name,x.model_name,x.language_hint) for x in extract_document_links(html,url)][:8])
photos=extract_photos(html,url)
print('gallery',len(photos.photos),'thumbs',len(photos.thumbnails),'3d',len(photos.three_d))
print('api_markers',[(needle,html.lower().count(needle)) for needle in ('/api/','api.samsung.com','graphql','apiChangeModelCode','digitalData','modelCode','contentsfile.aspx')])
