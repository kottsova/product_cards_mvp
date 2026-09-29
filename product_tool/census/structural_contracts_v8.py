"""Stage 8 structural contracts, intentionally independent of CMS and product values."""
import hashlib
import json
import re
from urllib.parse import urljoin, urlsplit
from bs4 import BeautifulSoup
from .search_routes import safe_url
from .search_snapshots import sanitized_url
from .discovery import json_ld_products, detect_internal_search
from .fingerprint import fingerprint_platform

LAYERS = ('discovery','identity','specifications','media','documents')
IDENTITY = {'sku','mpn','model','gtin','gtin8','gtin12','gtin13','gtin14','name','color','size','memory','revision','serviceIndex','configuration','productID','inProductGroupWithID','hasVariant','isVariantOf'}
SECRET = re.compile(r'token|session|password|authorization|cookie|email|customer|user_id|nonce|csrf',re.I)

def digest(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':')).encode()).hexdigest()

def key_paths(value, prefix='', depth=0):
    if depth>8:return []
    if isinstance(value,dict):
        return sorted({p for key,child in value.items() if not SECRET.search(key) and re.fullmatch(r'[@A-Za-z_][A-Za-z_0-9@-]{0,60}',key) for p in [prefix+'.'+key,*key_paths(child,prefix+'.'+key,depth+1)]})
    if isinstance(value,list):return sorted({p for child in value[:20] for p in key_paths(child,prefix+'[]',depth+1)})
    return []

def inspect_structure(html,url,hosts, *, sanitized=False):
    soup=BeautifulSoup(html,'html.parser'); products=list(json_ld_products(html))
    product_nodes=soup.select('[itemscope][itemtype*="schema.org/Product"]')
    fields=sorted({k for p in products for k in p if k in IDENTITY})
    paths=sorted({x for p in products for x in key_paths(p)})
    props=sorted({v for node in product_nodes for n in node.select('[itemprop]') for v in str(n.get('itemprop','')).split() if v in IDENTITY})
    is_product=(len(products)==1 and len(product_nodes)<=1) or (not products and len(product_nodes)==1)
    routes=detect_internal_search(html,url,allowed_hosts=tuple(hosts))
    links=[]
    for loc in soup.find_all('loc',limit=800):
        target=sanitized_url(loc.get_text(strip=True))
        if safe_url(target,tuple(hosts)):
            links.append({'url':target,'kind':'product' if re.search(r'/products?/.+|/p/|\.html$',urlsplit(target).path) else 'category','provenance':{'method':'sitemap_loc','parent_url':sanitized_url(url),'selector':'loc'}})
    for a in soup.select('a[href]'):
        target=sanitized_url(urljoin(url,a.get('href','')))
        if not safe_url(target,tuple(hosts)) or SECRET.search(target):continue
        path=urlsplit(target).path.lower(); text=a.get_text(' ',strip=True).lower()
        kind='support' if re.search(r'support|manual|download|help|service',path) else 'category' if re.search(r'categor|catalog|collection|shop|products/?$',path) else 'product' if re.search(r'/products?/.+|/p/|\.html$',path) else 'navigation'
        if re.search(r'login|account|cart|checkout|privacy|terms|contact|news|blog',path):continue
        links.append({'url':target,'kind':kind,'provenance':{'method':'first_party_navigation','parent_url':sanitized_url(url),'selector':'a[href]'}})
    for p in products:
        if isinstance(p.get('url'),str):
            target=sanitized_url(urljoin(url,p['url']))
            if safe_url(target,tuple(hosts)):links.insert(0,{'url':target,'kind':'product','provenance':{'method':'JSON-LD_Product.url','parent_url':sanitized_url(url),'selector':'Product.url'}})
    discovery={'routes':sorted({r.method+':'+r.query_parameter+':'+r.source for r in routes if r.executable}), 'navigation': sorted({l['kind'] for l in links}), 'pagination':sorted({ 'rel_next' for n in soup.select('[rel~=next]') } | {'page_parameter' for l in links if re.search(r'[?&]page=',l['url'])}), 'locale_contract':'path_prefix' if re.match(r'^/[a-z]{2}(?:[-_][a-z]{2})?/',urlsplit(url).path,re.I) else 'host_or_undeclared'}
    identity={'json_paths':[p for p in paths if p.split('.')[1].split('[')[0] in IDENTITY], 'microdata_properties':props, 'code_fields':sorted(set(fields+props)&{'sku','mpn','model','gtin','gtin13','productID'}), 'variant_fields':sorted(set(fields+props)&{'color','size','memory','revision','serviceIndex','configuration','hasVariant','isVariantOf','inProductGroupWithID'}), 'model_semantics':'unverified_sku_meaning' if 'sku' in fields and not {'mpn','model'}&set(fields) else 'explicit_manufacturer_or_model' if {'mpn','model'}&set(fields) else 'marketing_name_only'}
    specs={'json_paths':[p for p in paths if re.search(r'additionalProperty|PropertyValue|technical|specification',p,re.I)],'dom_semantics':sorted({'table:tr:th+td' for t in soup.select('table') if t.select('th') and t.select('td')} | {'dl:dt+dd' for t in soup.select('dl') if t.select('dt') and t.select('dd')} | {'accordion:details+summary' for t in soup.select('details') if t.select('summary')})}
    media={'json_paths':[p for p in paths if re.search(r'\.image|\.video',p)],'dom_semantics':sorted({'responsive_srcset' for n in soup.select('img[srcset],source[srcset]')} | {'semantic_gallery' for n in soup.select('[itemprop=image]')}),'resolution_rule':'Select largest explicitly advertised srcset width/density or ImageObject.contentUrl; never invent CDN transforms or download media sets.'}
    document_links=[a for a in soup.select('a[href]') if re.search(r'\.pdf(?:[?#]|$)',a['href'],re.I)]
    docs={'link_schema':sorted({'a[href:pdf]' for a in soup.select('a[href]') if re.search(r'\.pdf(?:[?#]|$)',a['href'],re.I)} | {'a[hreflang]' for a in document_links if a.get('hreflang')}),'support_navigation':any(l['kind']=='support' for l in links),'model_linkage':'unverified: require model-specific support association; a PDF link alone is insufficient','language_contract':'explicit_hreflang' if any(a.get('hreflang') for a in document_links) else 'unknown_do_not_infer_from_locale'}
    contracts={'discovery':discovery,'identity':identity,'specifications':specs,'media':media,'documents':docs}
    # Identity-critical context prevents a bare Product field set/CMS from creating reuse.
    signatures={layer:digest({'contract':contract,'identity_semantics':identity['model_semantics'],'variant_contract':identity['variant_fields'],'pagination':discovery['pagination'],'locale':discovery['locale_contract']}) for layer,contract in contracts.items()}
    observed={'discovery':bool(links or discovery['routes']),'identity':is_product and bool(fields or props),'specifications':bool(specs['json_paths'] or specs['dom_semantics']),'media':bool(media['json_paths'] or media['dom_semantics']),'documents':bool(docs['link_schema'])}
    cms=[x.to_dict() for x in fingerprint_platform(html)]
    return {'is_product_page':is_product,'product_objects':len(products)+len(product_nodes),'contracts':contracts,'signatures':signatures,'observed':observed,'cms_fingerprint':cms,'links':list({l['url']:l for l in links}.values())[:300], 'sanitized_snapshot_limitations':sanitized,'content_sha256':hashlib.sha256(html.encode()).hexdigest(),'fixture_version':2}

def cluster_profiles(profiles):
    result={layer:[] for layer in LAYERS}
    for layer in LAYERS:
        groups={}
        for p in profiles:
            evidence=p['layers'][layer]
            if not evidence.get('observed') or not p.get('sample_product_page') or p['completeness_status'] in {'http_blocked','javascript_only'}:continue
            # Unresolved variant/model semantics prohibit shared identity contracts.
            key=evidence['signature']
            if not evidence.get('contract_reviewed'):key+=':'+p['profile_id']
            if layer=='identity' and evidence['contract']['model_semantics']!='explicit_manufacturer_or_model':key+=':'+p['source_family']
            groups.setdefault(key,[]).append(p)
        for key,members in groups.items():
            families={p['source_family'] for p in members}; fixtures={p['layers'][layer].get('fixture') for p in members}
            independent=len(families)>1
            regional=len(members)>1 and len({p['official_domain'] for p in members})>1
            validated=all(p['layers'][layer].get('fixture') and p['layers'][layer].get('contract_reviewed') for p in members)
            status='shared_adapter_candidate' if independent and validated else 'regional_shared_candidate' if regional and validated else 'custom_adapter_candidate'
            result[layer].append({'cluster_id':layer+'_'+digest(key)[:12],'status':status,'members':[p['profile_id'] for p in members],'source_families':sorted(families),'compatibility_evidence':{'identical_normalized_contract':True,'mandatory_identity_and_variant_context_in_signature':True,'locale_pagination_context_in_signature':True,'fixture_refs':sorted(x for x in fixtures if x),'contract_reviewed':validated,'CMS_used_for_grouping':False},'production_ready':False})
    return result
