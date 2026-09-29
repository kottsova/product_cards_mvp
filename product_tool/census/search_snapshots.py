"""SourceSnapshot persistence and hash-checked response replay for diagnostic discovery."""
from contextlib import closing
import hashlib
import json
import sqlite3
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit
from bs4 import BeautifulSoup
from product_tool import storage
from product_tool.fetch_history import record_fetch_attempt, save_source_snapshot
from .search_routes import SECRET, STATIC_PARAMETERS, redact_url
from .endpoint_probe import ProbeResult
from .models import AccessStatus, ProtectionStatus, EndpointCapability

SANITIZER_VERSION = '2'
PERSONAL_KEYS = {'email','username','user','userid','user_id','customer','customerid','phone','address'}


def sanitized_url(value):
    try:
        p=urlsplit(value)
        query=[(k,v) for k,v in parse_qsl(p.query,keep_blank_values=True) if not SECRET.search(k) and k.lower() not in PERSONAL_KEYS]
        return redact_url(urlunsplit((p.scheme,p.netloc,p.path,urlencode(query),'')))
    except ValueError:return ''


def sanitize_html(html, *, extra_attributes=()):
    soup=BeautifulSoup(html,'html.parser')
    for script in soup.find_all('script'):
        if (script.get('type') or '').lower()!='application/ld+json':
            script.decompose();continue
        try:value=json.loads(script.string or script.get_text())
        except (ValueError,TypeError):script.decompose();continue
        def scrub(value):
            if isinstance(value,dict):return {k:scrub(v) for k,v in value.items() if k in {'@type','@graph','itemListElement','item','url','name','sku','mpn','model','gtin','gtin8','gtin12','gtin13','gtin14','color','size','productGroupID','inProductGroupWithID','storage','memory','ram','revision','hardwareRevision','serviceIndex','region','configuration'}}
            if isinstance(value,list):return [scrub(x) for x in value]
            if isinstance(value,str) and value.startswith(('https://','http://','/')):return sanitized_url(value)
            return value
        script.string=json.dumps(scrub(value))
    for tag in soup.find_all(True):
        for key in list(tag.attrs):
            if key not in set(extra_attributes) | {'class','id','itemtype','itemscope','itemprop','data-product-id','data-product-handle','data-sku','href','action','method','name','type','value','formaction','formmethod','rel','disabled'} and not key.lower().startswith('on'):
                del tag.attrs[key]
                continue
            if key.lower().startswith('on'):
                tag[key]='[handler omitted]'
            elif key in {'href','action','src','formaction'}:
                raw=tag.get(key)
                if isinstance(raw,str):
                    clean=sanitized_url(raw)
                    if key in {'action','formaction'} and (SECRET.search(raw) or any(k.lower() in PERSONAL_KEYS for k,v in parse_qsl(urlsplit(raw).query))):
                        clean=clean.split('?')[0]+'?csrf=[redacted]'
                    tag[key]=clean
            elif SECRET.search(key):tag[key]='[redacted]'
        if tag.name in {'input','textarea'} and tag.get('name','').lower() not in STATIC_PARAMETERS:
            tag['value']='[redacted]';tag.clear()
    return str(soup)


class SearchSnapshotStore:
    """An isolated DB using the existing FetchAttempt/SourceSnapshot tables."""
    def __init__(self,path):
        self.path=Path(path)
        storage.initialize(self.path)

    def writer(self,expected,source_family):
        with storage._connection(self.path) as c:
            c.execute("INSERT OR IGNORE INTO batches(id,filename,sheet_name,mapping_json,confirmed_at) VALUES ('stage5_1','catalog_2026-09-21_filtered.xlsx','diagnostic','{}','now')")
            row=c.execute("SELECT id FROM products WHERE batch_id='stage5_1' AND search_code=? AND brand=?",(expected.seller_sku,expected.brand_raw)).fetchone()
            if row:product_id=row[0]
            else:
                c.execute("INSERT INTO products(batch_id,row_number,name,brand,search_code,alternate_code,category,needs_confirmation,issues_json,original_values_json) VALUES ('stage5_1',(SELECT COALESCE(MAX(row_number),0)+1 FROM products WHERE batch_id='stage5_1'),?,?,?,'',?,0,'[]','[]')",(expected.title_raw,expected.brand_raw,expected.seller_sku,expected.category_raw))
                product_id=c.execute('SELECT last_insert_rowid()').fetchone()[0]
        def save(response,identity_key):
            if response.access_status not in {AccessStatus.DIRECT_ACCESS,AccessStatus.JAVASCRIPT_REQUIRED}:return None
            content=sanitize_html(response.diagnostic_text)
            meta={'identity_key':identity_key,'sanitizer_version':SANITIZER_VERSION,'requested_url':sanitized_url(response.url),'final_url':sanitized_url(response.final_url),'redirect_chain':[sanitized_url(x) for x in response.redirect_chain],'capability':response.capability.value,'sample_type':response.sample_type,'access_status':response.access_status.value,'protection_status':response.protection_status.value,'javascript_required':response.javascript_required,'http_status':response.http_status,'checked_at':response.checked_at}
            attempt=record_fetch_attempt(self.path,product_id,source_family,status='success',requested_url=meta['requested_url'],final_url=meta['final_url'],http_status=response.http_status)
            sid=save_source_snapshot(self.path,product_id,source_family,attempt,source_url=meta['final_url'],content=content,extracted=meta,content_type=response.content_type,fetched_at=response.checked_at)
            return {'snapshot_id':sid,'store':self.path.name,'content_sha256':hashlib.sha256(content.encode()).hexdigest(),'requested_url':meta['requested_url'],'sample_type':response.sample_type}
        return save

    def load(self,ref):
        if ref.get('store')!=self.path.name:raise ValueError('snapshot_store_mismatch')
        with closing(sqlite3.connect(self.path.resolve().as_uri()+'?mode=ro',uri=True)) as c:
            c.row_factory=sqlite3.Row
            row=c.execute('SELECT * FROM source_snapshots WHERE id=?',(ref['snapshot_id'],)).fetchone()
        if row is None:raise ValueError('snapshot_missing')
        row=dict(row)
        digest=hashlib.sha256(row['content'].encode()).hexdigest()
        if digest!=row['content_sha256'] or digest!=ref['content_sha256']:raise ValueError('snapshot_hash_mismatch')
        row['extracted']=json.loads(row.pop('extracted_json'))
        return row


def response_from_snapshot(snapshot,identity_key):
    metadata=snapshot['extracted']
    if metadata['identity_key']!=identity_key:raise ValueError('snapshot_scope_mismatch')
    return ProbeResult(url=metadata['requested_url'],final_url=metadata['final_url'],redirect_chain=tuple(metadata['redirect_chain']),capability=EndpointCapability(metadata['capability']),sample_type=metadata['sample_type'],access_status=AccessStatus(metadata['access_status']),protection_status=ProtectionStatus(metadata['protection_status']),http_status=metadata['http_status'],javascript_required=metadata['javascript_required'],content_type=snapshot['content_type'],protection_evidence=(),product_search_available=None,fingerprints=(),evidence=(),checked_at=metadata['checked_at'],diagnostic_text=snapshot['content'])
