"""Stage 5.1 result admission and ranking, independent of identity validation."""
import json
import re
from urllib.parse import urljoin, urlsplit, unquote, parse_qsl
from .search_routes import SearchHTMLParser, FLOW, safe_url, redact_url
from .sitemap_strategy import CandidatePage, normalize_candidate_url

PRODUCT_SEGMENTS = {'product', 'products', 'p', 'mkt-product'}
SERVICE_SEGMENTS = {'product-support', 'support', 'pages', 'blog', 'blogs', 'news', 'policies', 'policy', 'about', 'contact', 'returns', 'warranty', 'delivery', 'category', 'categories', 'collections', 'search'}


def path_signals(url, configured_product_patterns=()):
    path = unquote(urlsplit(url).path).lower()
    segments = [x for x in path.split('/') if x]
    service = not segments or any(x in SERVICE_SEGMENTS or any(x.startswith(k+'-') for k in ('contact', 'returns', 'warranty', 'delivery', 'about')) for x in segments)
    service |= len(segments) == 1 and bool(re.fullmatch(r'[a-z]{2}(?:-[a-z]{2})?', segments[0]))
    product = not service and any(x in PRODUCT_SEGMENTS and i+1 < len(segments) for i,x in enumerate(segments))
    # Declarative complete path prefixes, never hostname/brand substring bonuses.
    configured = not service and any(prefix.startswith('/') and prefix.endswith('/') and path.startswith(prefix.lower()) and len(path)>len(prefix) for prefix in configured_product_patterns)
    return product, service, configured


def parse_search_results(html, *, response_url, expected, source_family, allowed_hosts, category_hints=(), limit=20, max_bytes=1000000, configured_product_patterns=(), audit=None):
    from .internal_search_strategy import generate_search_queries, _exact_token
    parser=SearchHTMLParser();parser.feed(html[:max_bytes])
    entries=[{'href':x['attrs'].get('href') or '', 'title':x['text'], 'type':'html_product_card' if x.get('card_evidence') else 'generic_first_party_anchor', 'card':x.get('card_evidence')} for x in parser.links]
    def has_type(node, name):
        value=node.get('@type')
        return value==name or isinstance(value,list) and name in value
    def visit(value,depth=0):
        if depth>8 or len(entries)>=1200:return
        if isinstance(value,list):
            for node in value[:200]:visit(node,depth+1)
        elif isinstance(value,dict):
            if has_type(value,'ItemList'):
                items=value.get('itemListElement',[])
                if isinstance(items,list):
                    for card in items[:200]:
                        item=card.get('item',card) if isinstance(card,dict) else card
                        href=item.get('url','') if isinstance(item,dict) else item
                        if not isinstance(href,str):continue
                        try: product,service,configured=path_signals(urljoin(response_url,href),configured_product_patterns)
                        except ValueError:continue
                        is_product=isinstance(item,dict) and has_type(item,'Product')
                        entries.append({'href':href,'title':str(item.get('name','')) if isinstance(item,dict) else '', 'type':'json_ld_itemlist_product' if is_product or product or configured else 'generic_first_party_anchor', 'card':None})
            visit(value.get('@graph',[]),depth+1)
    for script in parser.scripts:
        if script['attrs'].get('type','').lower()=='application/ld+json':
            try:visit(json.loads(script['text']))
            except (ValueError,TypeError,RecursionError):pass
    candidates={};rejected={}
    queries=generate_search_queries(expected)
    def reject(url,reason):rejected.setdefault(url,reason)
    for entry in entries[:1200]:
        href=entry['href'];title=entry['title'][:300]
        if not href.strip() or href.startswith('#'):continue
        try:url=normalize_candidate_url(urljoin(response_url,href))
        except ValueError:continue
        parsed=urlsplit(url);path=unquote(parsed.path)
        if not safe_url(url,allowed_hosts):reject(redact_url(url),'foreign_or_unsafe_url');continue
        if FLOW.search(path) or re.search(r'\.(?:pdf|jpe?g|png|gif|webp|svg|css|js|zip|mp4)$',path,re.I):reject(url,'excluded_flow_or_asset');continue
        if 'search' in path.lower().split('/'):
            reject(url,'search_route_not_product');continue
        model_url_evidence=parsed.path+' '+ ' '.join(v for k,v in parse_qsl(parsed.query) if k.lower() in {'sku','mpn','model','productcode'})
        url_models=tuple(x['query'] for x in queries if _exact_token(x['query'],model_url_evidence))
        title_models=tuple(x['query'] for x in queries if _exact_token(x['query'],title))
        product,service,configured=path_signals(url,configured_product_patterns)
        if service and not (url_models or title_models):reject(url,'navigation_or_service_without_exact_model');continue
        if url==normalize_candidate_url(response_url):reject(url,'search_response_self_link');continue
        structured=entry['type'] in {'html_product_card','json_ld_itemlist_product'}
        if not (url_models or title_models or product or configured or structured):reject(url,'no_strong_product_evidence');continue
        score=15;reasons=['canonical_first_party_host:+15'];evidence=[]
        def add(kind,weight,**detail):
            nonlocal score
            score+=weight;reasons.append(f'{kind}:+{weight}')
            evidence.append({'type':kind,'ranking_only':True,**detail})
        if product:add('product_like_path',25)
        if configured:add('configured_product_pattern',25)
        if url_models:add('exact_model_in_result_url',70)
        if title_models:add('exact_model_in_result_title',80)
        if structured:add(entry['type'],20,**({'container':entry['card']} if entry['card'] else {}))
        else:evidence.append({'type':'generic_first_party_anchor','ranking_only':True})
        if service:
            score-=30;reasons.append('service_path_retained_only_for_exact_model:-30')
        categories=tuple(x for x in category_hints if len(x)>=3 and x.casefold() in path.casefold())
        for hint in categories:add('category_hint',12,value=hint)
        evidence.append({'type':'search_result_context','response_url':redact_url(response_url),'title':title,'ranking_only':True})
        c=CandidatePage(url,'',source_family,'internal_search',score,tuple(reasons),categories,url_models,tuple(evidence))
        if url not in candidates or score>candidates[url].ranking_score:candidates[url]=c
    if audit is not None:
        audit.update({'links_examined':len(entries),'unique_admitted':len(candidates),'rejected_links':[{'url':redact_url(k),'reason':v} for k,v in sorted(rejected.items()) if k not in candidates], 'navigation_service_excluded':sum(v=='navigation_or_service_without_exact_model' and k not in candidates for k,v in rejected.items())})
    return tuple(sorted(candidates.values(),key=lambda c:(-c.ranking_score,c.url))[:min(20,limit)])
