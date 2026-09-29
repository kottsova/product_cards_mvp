from pathlib import Path
import gzip,hashlib,json,sqlite3
from urllib.parse import urljoin
from bs4 import BeautifulSoup
root=Path('reports/lg_live_batch_2026-09-29_stage49')
c=sqlite3.connect('data/batches.sqlite3');c.row_factory=sqlite3.Row
out=[]
for pid,filename in [(10,'003_3feb3be362.gz'),(15,'007_1935ac5e38.gz')]:
 path=Path('reports/lg_live_batch_2026-09-28_stage43/step3b_data/raw')/filename
 raw=gzip.open(path,'rb').read();html=raw.decode('utf8')
 doc=c.execute('select direct_url,source_url from product_documents where product_id=?',(pid,)).fetchone()
 links={urljoin(doc['source_url'],a.get('href','')) for a in BeautifulSoup(html,'html.parser').select('a[href]')}
 out.append({'product_id':pid,'saved_support_path':str(path),'saved_support_sha256':hashlib.sha256(raw).hexdigest(),
             'document_url':doc['direct_url'],'document_url_is_href_on_support_page':doc['direct_url'] in links})
assert all(x['document_url_is_href_on_support_page'] for x in out)
root.joinpath('manual_link_audit.json').write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding='utf8')
print(out)
