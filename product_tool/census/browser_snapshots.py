"""Sanitized rendered DOM storage using existing immutable SourceSnapshot tables."""
from bs4 import BeautifulSoup,Comment
import hashlib
import json
from product_tool import storage
from product_tool.fetch_history import record_fetch_attempt,save_source_snapshot
from .search_snapshots import SearchSnapshotStore,sanitize_html
from .browser_contracts import SEARCH_WORD,VERSIONS
from .browser_projection import sanitize_projection
from .search_routes import redact_url


def sanitize_browser_dom(html):
    soup=BeautifulSoup(html,'html.parser')
    for n in soup.find_all(True):
        label=n.get('aria-label','')
        if n.get('id'):
            label+=' '+' '.join(x.get_text(' ',strip=True) for x in soup.find_all('label',attrs={'for':n['id']}))
        if SEARCH_WORD.search(label):n['aria-label']='Search'
        else:n.attrs.pop('aria-label',None)
        if n.get('role') not in {'search','searchbox','navigation','dialog'}:n.attrs.pop('role',None)
        n.attrs.pop('id',None);n.attrs.pop('for',None)
        if n.get('itemprop') not in {'model','sku','mpn','color','size','storage','ram','revision','serviceIndex','region','configuration','productGroupID'}:n.attrs.pop('content',None)
    for comment in soup.find_all(string=lambda x:isinstance(x,Comment)):comment.extract()
    for element in soup.find_all(['style','noscript']):element.decompose()
    return sanitize_html(str(soup),extra_attributes=('role','aria-label','content'))


class BrowserSnapshotStore(SearchSnapshotStore):
    def writer(self,expected,source_family):
        with storage._connection(self.path) as c:
            c.execute("INSERT OR IGNORE INTO batches(id,filename,sheet_name,mapping_json,confirmed_at) VALUES ('stage6','catalog_2026-09-21_filtered.xlsx','diagnostic','{}','now')")
            row=c.execute("SELECT id FROM products WHERE batch_id='stage6' AND search_code=? AND brand=?",(expected.seller_sku,expected.brand_raw)).fetchone()
            if row:pid=row[0]
            else:
                c.execute("INSERT INTO products(batch_id,row_number,name,brand,search_code,alternate_code,category,needs_confirmation,issues_json,original_values_json) VALUES ('stage6',(SELECT COALESCE(MAX(row_number),0)+1 FROM products WHERE batch_id='stage6'),?,?,?,'',?,0,'[]','[]')",(expected.title_raw,expected.brand_raw,expected.seller_sku,expected.category_raw))
                pid=c.execute('SELECT last_insert_rowid()').fetchone()[0]
        def save(state,phase,query,scope):
            projection=sanitize_projection(state['projection'])
            for descriptor in projection.get('inputs',[]):descriptor.pop('index',None)
            content=json.dumps(projection,ensure_ascii=False,sort_keys=True,separators=(',',':'))
            meta={**VERSIONS,**state.get('versions',{}),'identity_key':scope,'source_family':source_family,'product_identity':expected.to_dict(),'phase':phase,'query':query,'render_mode':state.get('render_mode','interactive_search_ui'),'javascript_errors':state.get('javascript_errors',0),'final_url':redact_url(state['url']),'requested_url':redact_url(state.get('requested_url',state['url'])),'fragment_types':sorted({f['type'] for f in projection.get('fragments',[])}),'content_sha256':hashlib.sha256(content.encode()).hexdigest(),'network_counts':state.get('counts',{}),'projection_bytes':len(content.encode())}

            attempt=record_fetch_attempt(self.path,pid,source_family,status='success',requested_url=meta['final_url'],final_url=meta['final_url'])
            sid=save_source_snapshot(self.path,pid,source_family,attempt,source_url=meta['final_url'],content=content,extracted=meta,content_type='application/vnd.product-search-projection+json')
            return {'snapshot_id':sid,'store':self.path.name,'content_sha256':hashlib.sha256(content.encode()).hexdigest(),'phase':phase,'query':query,'url':meta['final_url']}
        return save
