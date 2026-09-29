"""Typed projection parser bridge and explicit offline legacy snapshot conversion."""
import html
import json
import re
from bs4 import BeautifulSoup
from .browser_contracts import VERSIONS,detect_search_ui
from .search_routes import safe_url,redact_url


def projection_html(projection):
    """Construct only whitelisted semantic markup for existing Stage 5.1 parsers."""
    parts=[]
    for fragment in projection.get('fragments',[]):
        kind=fragment.get('type')
        if kind=='result_link':
            a='<a href="'+html.escape(fragment['url'],quote=True)+'">'+html.escape(fragment.get('title',''))+'</a>'
            parts.append('<div class="product-card">'+a+'</div>' if fragment.get('local_card') else a)
        elif kind=='json_ld':
            parts.append('<script type="application/ld+json">'+json.dumps(fragment['data'],ensure_ascii=True).replace('<','\\u003c')+'</script>')
        elif kind=='microdata':
            parts.append('<div itemscope itemtype="https://schema.org/Product">'+''.join('<meta itemprop="'+html.escape(k,quote=True)+'" content="'+html.escape(str(v),quote=True)+'">' for k,v in fragment['data'].items())+'</div>')
    return ''.join(parts)


def validate_projection(projection,budget):
    if projection.get('overflow'):raise ValueError('projection_budget_exhausted')
    if projection.get('projection_version')!=VERSIONS['projection_version']:raise ValueError('checkpoint_incompatible')
    fragments=projection.get('fragments',[]);inputs=projection.get('inputs',[])
    if len(json.dumps(projection,ensure_ascii=False,separators=(',',':')).encode())>budget.max_projection_bytes or len(fragments)>budget.max_projection_fragments or any(len(json.dumps(x,ensure_ascii=False,separators=(',',':')).encode())>budget.max_fragment_bytes for x in fragments+inputs):raise ValueError('projection_budget_exhausted')


def legacy_projection(html_text,url,hosts,visible_indices=None,queries=()):
    """Offline-only migration of already sanitized Stage 6 HTML; not a live DOM path.

    Visibility is historical evidence, never inferred for a live submission.
    Also useful for fake browser fixtures. No browser/network imports.
    """
    soup=BeautifulSoup(html_text,'html.parser')
    ui,outcome=detect_search_ui(html_text,url,hosts,visible_indices=visible_indices)
    inputs=[ui|{'unsafe':False,'visible':True}] if ui else ([{'unsafe':True}] if outcome=='browser_search_ui_unsafe' else [])
    for e in soup.select('nav,header,footer,aside,[role="navigation"]'):e.decompose()
    fragments=[]
    for a in soup.select('a[href]'):
        from urllib.parse import urljoin
        target=urljoin(url,a['href'])
        if not safe_url(target,hosts):continue
        card=a.find_parent(class_=re.compile('product-card|card-product|product-item|search-result|result-item'))
        from .search_results import path_signals
        title=a.get_text(' ',strip=True)[:300]
        if card is None and not path_signals(target)[0] and not any(q.casefold() in (title+' '+target).casefold() for q in queries):continue
        fragments.append({'type':'result_link','url':redact_url(target),'title':a.get_text(' ',strip=True)[:300],'local_card':card is not None})
    from .search_snapshots import sanitize_html
    clean=BeautifulSoup(sanitize_html(str(soup)),'html.parser')
    for e in clean.select('script[type="application/ld+json"]'):
        try:fragments.append({'type':'json_ld','data':json.loads(e.string or '')})
        except ValueError:pass
    for root in soup.select('[itemscope][itemtype]'):
        if root.get('itemtype','').rstrip('/') not in {'https://schema.org/Product','http://schema.org/Product'}:continue
        values={}
        for e in root.select('[itemprop]'):
            if e.find_parent(attrs={'itemscope':True}) is not root:continue
            for k in e.get('itemprop','').split():
                if k in {'model','sku','mpn','color','size','storage','ram','revision','serviceIndex','region','configuration','productGroupID'}:values[k]=e.get('content',e.get_text(' ',strip=True))[:300]
        fragments.append({'type':'microdata','data':values})
    return {'projection_version':VERSIONS['projection_version'],'url':redact_url(url),'title':'','inputs':inputs,'fragments':fragments,'protection':bool(re.search(r'verify (?:that )?you are human|access denied|unusual traffic|checking your browser',soup.get_text(' ',strip=True),re.I)),'cookie_dialog':{'visible':False},'metrics':{'dom_elements':len(soup.find_all(True)),'fragment_count':len(fragments)},'origin':'offline_legacy_conversion'}


def sanitize_projection(projection):
    """Defensive snapshot boundary: only the documented schema is persisted."""
    from .search_snapshots import sanitized_url
    def text(value):return str(value or '')[:300]
    def structured(value,depth=0):
        if depth>8:return None
        if isinstance(value,list):return [structured(x,depth+1) for x in value[:100]]
        if not isinstance(value,dict):return text(value) if isinstance(value,(str,int,float)) else None
        keys={'@type','@graph','itemListElement','item','name','model','sku','mpn','color','size','storage','ram','revision','serviceIndex','region','configuration','productGroupID','url'}
        return {k:(sanitized_url(v) if k=='url' and isinstance(v,str) else structured(v,depth+1)) for k,v in value.items() if k in keys}
    out={k:projection[k] for k in ('projection_version','protection','origin') if k in projection}
    out.update(url=sanitized_url(projection.get('url','')),title=text(projection.get('title','')),inputs=[],fragments=[],cookie_dialog={'visible':bool(projection.get('cookie_dialog',{}).get('visible'))},metrics={k:v for k,v in projection.get('metrics',{}).items() if k in {'dom_elements','links_examined','fragment_count','projection_bytes'} and type(v) is int})
    keys={'type','role','label','form_present','action_host','action_path','form_action','submit_method','visible','password_input','file_input','security_input','unsafe','discovery_method','selector_description','originating_url'}
    for descriptor in projection.get('inputs',[]):
        out['inputs'].append({k:(sanitized_url(v) if k in {'form_action','originating_url'} else v if isinstance(v,bool) else text(v)) for k,v in descriptor.items() if k in keys})
    for fragment in projection.get('fragments',[]):
        kind=fragment.get('type')
        if kind=='result_link':out['fragments'].append({'type':kind,'url':sanitized_url(fragment['url']),'title':text(fragment.get('title','')),'local_card':bool(fragment.get('local_card'))})
        elif kind in {'json_ld','microdata'}:out['fragments'].append({'type':kind,'data':structured(fragment['data'])})
    return out
