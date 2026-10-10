"""HyperX route binding to the shared search/sitemap parsers, not a search engine."""
from urllib.parse import urljoin, urlsplit
from bs4 import BeautifulSoup
from ..identity import ProductIdentity
from ..census.discovery import detect_internal_search
from ..census.search_results import parse_search_results
from ..census.sitemap_strategy import parse_catalog_document, robots_sitemap_declarations, rank_candidate_url
from ..census.search_routes import safe_url
from .common import utc_now

HOSTS=('hyperx.com','www.hyperx.com','row.hyperx.com','uk.hyperx.com')

def model_query(name):
    return name.split('[',1)[0].strip().removesuffix(' Wired')

class HyperXDiscovery:
    def __init__(self, fetch, emit):
        self.fetch,self.emit=fetch,emit

    def candidates(self, code, name, category, deadline):
        model=model_query(name)
        expected=ProductIdentity('HyperX','hyperx',category,'generic',code,'',name,(model,) if model else ())
        queries=list(dict.fromkeys(q for q in (code,code.split('#')[0],model) if q))
        seen=set()
        # These are catalog roots, not model URLs. Other regions are admitted only by homepage links.
        home=self.fetch('https://hyperx.com/',deadline)
        soup=BeautifulSoup(home,'html.parser')
        roots=['https://hyperx.com/']
        linked={urlsplit(urljoin(roots[0],a['href'])).hostname for a in soup.select('a[href]')}
        if '#' in code:
            for host in ('row.hyperx.com','uk.hyperx.com'):
                if host in linked:roots.append('https://'+host+'/')
        for root in roots:
            html=home if root==roots[0] else self.fetch(root,deadline)
            host=urlsplit(root).hostname
            routes=detect_internal_search(html,root,allowed_hosts=HOSTS)
            route=next((r for r in routes if r.executable),None)
            if route:
                for query in queries:
                    url=route.query_url(query)
                    self.emit(dict(event='hyperx_query',query=query,provider='official_catalog_search',url=url,region=host,source_type='search',accepted=False,reason='discovery_only',identity_relation='unverified'))
                    response=self.fetch(url,deadline)
                    found=parse_search_results(response,response_url=url,expected=expected,source_family='hyperx',allowed_hosts=HOSTS,limit=12)
                    for c in found:
                        if '/products/' not in urlsplit(c.url).path or c.url in seen:continue
                        score,_,_,models=rank_candidate_url(c.url,expected=expected,source_family='hyperx',allowed_hosts=HOSTS)
                        # A query hit is a candidate, never proof; reject clearly unrelated catalog cards.
                        if not models and code not in c.to_dict().get('anchor_text','').upper():continue
                        seen.add(c.url)
                        yield c.url,query,'official_catalog_search',host
            robots=self.fetch(urljoin(root,'robots.txt'),deadline)
            maps=list(robots_sitemap_declarations(robots))[:1]
            pending=list(maps);documents=0
            while pending and documents<3:
                url=pending.pop(0)
                if not safe_url(url,HOSTS):continue
                documents+=1
                try:kind,locs,_=parse_catalog_document(self.fetch(url,deadline),max_urls=2500)
                except ValueError:continue
                if kind=='sitemapindex':
                    pending.extend(v for v in locs if 'products' in v)
                    continue
                ranked=[]
                for location in locs:
                    if not safe_url(location,HOSTS) or '/products/' not in urlsplit(location).path:continue
                    score,_,_,models=rank_candidate_url(location,expected=expected,source_family='hyperx',allowed_hosts=HOSTS)
                    if models:ranked.append((score,location))
                for _,location in sorted(ranked,reverse=True)[:4]:
                    if location in seen:continue
                    seen.add(location)
                    self.emit(dict(event='hyperx_query',query=model,provider='official_sitemap',url=location,region=host,source_type='pdp_candidate',accepted=False,reason='sitemap_loc_only',identity_relation='unverified'))
                    yield location,model,'official_sitemap',host
        self.emit(dict(event='hyperx_official_miss',query=code,provider='official',url='',region='',source_type='discovery',accepted=False,reason='bounded official search complete; support/external/dealer remain separate',identity_relation='unverified'))
