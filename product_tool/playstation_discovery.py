"""Bounded link discovery using existing sitemap and browser-search primitives."""
import json,re
from urllib.parse import urljoin, urlsplit, urlunsplit, unquote, urlencode
from bs4 import BeautifulSoup
from .playstation_identity import codes, official, model_key
from .lg_sitemap_discovery import parse_sitemap

def canonical_url(url):
    p=urlsplit(url)
    return urlunsplit((p.scheme,p.netloc,p.path,'',''))

def query_variants(article, name):
    exact=next(iter(codes(article)), '')
    normalized=re.sub(r'[^A-Z0-9]','',exact or article.upper())
    family=re.sub(r'[AB]$','',exact) if re.fullmatch(r'CFI-\d{4}[AB]',exact) else exact
    sku=article.upper() if re.fullmatch(r'\d+-[A-Z]{2}',article.upper()) else ''
    return list(dict.fromkeys(x for x in (exact,normalized,sku,name,f'{article} PlayStation',f'{family} {name}') if x))

def identifier_relation(requested, returned):
    if requested==returned:return 'exact_cfi'
    a,b=re.fullmatch(r'CFI-(\d{2})(\d{2})([AB])',requested),re.fullmatch(r'CFI-(\d{2})(\d{2})([AB])',returned)
    if a and b:
        if a.groups()==b.groups(): return 'exact_cfi'
        if a[1]==b[1] and a[3]==b[3]:return 'regional_suffix'
        if a[1]==b[1]:return 'same_family_other_drive'
        return 'nearby_revision'
    if requested.startswith('CFI-') and returned.startswith('CFI-'):
        return 'same_family' if re.sub(r'\d','',requested)==re.sub(r'\d','',returned) else 'different_hardware'
    return 'retail_sku' if re.fullmatch(r'\d+-[A-Z]{2}',returned) else 'unproven'

def page_links(body, url):
    return list(dict.fromkeys(canonical_url(urljoin(url,a['href'])) for a in BeautifulSoup(body,'html.parser').select('a[href]') if official(urljoin(url,a['href']))))

def product_url(url):
    p=urlsplit(url)
    return official(url) and (('/buy-accessories/' in p.path or '/buy-consoles/' in p.path) and p.hostname=='direct.playstation.com' or '/product/' in p.path and '/accessories/' in p.path)

def rank_link(url, article, name, expected):
    slug=unquote(urlsplit(url).path).casefold()
    k=model_key(slug.replace('-',' '))
    if k!=expected:return -100
    score=5
    for t in re.findall(r'[a-z0-9]+',name.casefold()):
        if len(t)>2 and t not in {'playstation','controller','wireless','edition'} and t in slug:score+=2
    for variant in ('white','midnight black','fortnite','bundle','pro'):
        want=variant in name.casefold(); found=variant.replace(' ','-') in slug
        if want and found:score+=12
        elif found and variant in {'white','midnight black','fortnite','bundle'}:score-=12
    if any(t in slug for t in ('covers','charging-station','stick-module','usb-cable','vr2','edge','refurbished')):score-=25
    return score

def search_kind(url):
    if not official(url):return 'unknown'
    p=urlsplit(url)
    if '/support/hardware/' in p.path:return 'support'
    return 'product' if product_url(url) or any(x in p.path for x in ('/ps5/','/accessories/')) else 'unknown'

def direct_catalog_candidates(adapter, home, article, name, deadline):
    """Use the storefront's declared search route and GET endpoint, never an inferred SKU URL."""
    b=BeautifulSoup(home.text,'html.parser')
    node=b.select_one('input[data-searchurl]')
    if not node:return []
    route=urljoin(home.url,node['data-searchurl'])
    if not official(route) or urlsplit(route).hostname!='direct.playstation.com' or not urlsplit(route).path.rstrip('/').endswith('/search'):return []
    page=adapter.fetch(route,article,'playstation_direct_search','catalog',deadline)
    if not page:return []
    endpoint='';base='https://direct.playstation.com'
    for node in BeautifulSoup(page.text,'html.parser').select('[aemEndpoints],[aemendpoints]'):
        try:
            data=json.loads(node.get('aemendpoints') or node.get('aemEndpoints'))
            if data.get('getSearchDataMethod')=='GET':endpoint=data.get('getSearchDataUrl','')
        except (ValueError,TypeError):pass
    if not official(endpoint) or urlsplit(endpoint).hostname!='api.direct.playstation.com' or not urlsplit(endpoint).path.endswith('/products/search'):return []
    found=[]
    for query in (article,name):
        target=endpoint+('&' if '?' in endpoint else '?')+urlencode({'query':query})
        z=adapter.fetch(target,query,'playstation_direct_catalog','api',deadline)
        if not z:continue
        try:data=json.loads(z.text)
        except ValueError:continue
        for p in data.get('products',[])[:20]:
            u=canonical_url(urljoin(base,p.get('url','')))
            admitted=product_url(u)
            adapter.emit(query=query,provider='playstation_direct_catalog',url=u,region=urlsplit(u).path.split('/')[1] if admitted else '',source_type='api_result',accepted=admitted,reason='Public catalog link; own PDP identity still required' if admitted else 'Unsafe or non-product catalog URL',identity_relation='candidate_retail_sku' if p.get('code')==article else 'candidate_only',returned_sku=p.get('code',''))
            if admitted:found.append((0 if p.get('code')==article else 1,u))
        if any(priority==0 for priority,u in found):break
    return [u for priority,u in sorted(set(found))]

def external_candidates(log, article, name, callback, *, clock, deadline, factory=None):
    from .adapters.lg_browser_search import LGBrowserSearch
    from .census.browser_runtime import PlaywrightBrowser
    from .census.browser_contracts import BrowserBudget
    browser=(factory or (lambda: LGBrowserSearch(log,allowed_hosts=('www.playstation.com','direct.playstation.com','www.bing.com','bing.com','duckduckgo.com','www.google.com','google.com','gstatic.com'),official_host='www.playstation.com',official_hosts=('www.playstation.com','direct.playstation.com'),driver_factory=PlaywrightBrowser,budget=BrowserBudget(deadline_seconds=30,operation_timeout_seconds=10),candidate_classifier=search_kind)))()
    browser.trace_callback=callback
    found=[]
    try:
        queries=[f'site:playstation.com "{article}" {name}',f'site:direct.playstation.com {name}']
        for provider in ('bing','google'):
            for query in queries:
                if clock()>=deadline:break
                result=browser.search_provider(provider,query)
                found.extend(c.url for c in result.candidates)
                callback(dict(event='playstation_discovery',query=query,provider=provider+'_browser',url='',region='',source_type='search',accepted=bool(result.candidates),reason=result.outcome,identity_relation='candidate_only'))
                if found or result.outcome in {'challenge_detected','rate_limited','http_denied','host_stopped','runtime_unavailable'}:break
            if found:break
    finally:browser.close()
    return list(dict.fromkeys(found))
