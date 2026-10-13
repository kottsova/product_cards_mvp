"""All saved official gallery assets and byte evidence, independent of card selection."""
from __future__ import annotations
import time,re
import json
from datetime import datetime,timezone
from pathlib import Path
from urllib.parse import urlsplit,urlunsplit,parse_qsl,urlencode,unquote
from . import jobs,card_evidence,photo_metadata

ROLE_LABELS={'hero':'Главное фото','product_render':'Рендер товара','front':'Вид спереди','back':'Вид сзади','side':'Вид сбоку','detail':'Деталь','lifestyle':'В интерьере','technical_diagram':'Техническая схема','dimensions_diagram':'Схема размеров','accessories':'Аксессуары','station/dock':'База или станция','packaging':'Упаковка','bundle':'Комплект','unclassified_official_visual':'Официальное изображение; роль не определена'}

def normalized_asset(url):
    """Only documented rendition syntax; color, asset IDs and distinct angles remain."""
    p=urlsplit(url);host=(p.hostname or '').lower();path=p.path
    if host.endswith('razerzone.com'):
        nested=re.search(r'/(https%3A%2F%2F.+)$',path,re.I)
        if nested:
            origin=unquote(nested[1]);o=urlsplit(origin)
            if (o.hostname or '').endswith('.razer.com'):return normalized_asset(origin)
    if host.endswith('jbl.com') and '/on/demandware.static/' in path:
        path=path[path.index('/on/demandware.static/'):]
    if host.endswith('samsung.com'):
        path=re.sub(r'/\$[^/]+\$(?=/|$)','/$RENDITION$',path)
        path=re.sub(r'-thumb(?=-\d+$)','',path)
    if host.endswith(('shopify.com','hyperx.com','dreametech.com','dreame.tech')):
        path=re.sub(r'_\d+x\d*(?=\.[A-Za-z]+$)','',path)
    ignored={'width','height','wid','hei','w','h','sw','sh','fmt','sfrm','qlt','quality','dpr','fit','imwidth'}
    query=urlencode([(k,v) for k,v in parse_qsl(p.query,keep_blank_values=True) if k.lower() not in ignored])
    return urlunsplit(('https',host,path,query,''))

def published_origin(url):
    """A signed renderer URL explicitly publishes its upstream image URL."""
    p=urlsplit(url)
    if (p.hostname or '').endswith('.razerzone.com'):
        match=re.search(r'/(https%3A%2F%2F.+)$',p.path,re.I)
        if match:
            origin=unquote(match[1]);o=urlsplit(origin)
            if o.scheme=='https' and (o.hostname or '').endswith('.razer.com'):return origin
    return url

def role(photo):
    if photo.get('kind') in {'technical_diagram','dimensions_diagram','lifestyle','packaging','bundle','accessories'}:return photo['kind']
    text=(photo.get('role') or photo.get('url','')).casefold()
    for pattern,name in [(r'dimension|maß|габарит','dimensions_diagram'),(r'technical|diagram|схем','technical_diagram'),(r'packag|\bbox\b|box_image','packaging'),(r'bundle|комплект','bundle'),(r'accessor|аксесс','accessories'),(r'station|dock|base','station/dock'),(r'lifestyle|room|интерьер','lifestyle'),(r'hero','hero'),(r'front|перед','front'),(r'back|rear|зад','back'),(r'side|left|right|бок','side'),(r'detail|closeup','detail')]:
        if re.search(pattern,text):return name
    return 'product_render' if photo.get('kind')=='product_gallery' else 'unclassified_official_visual'

def evidence_kind(product):
    b=product['brand'].strip().casefold()
    return 'xiaomi' if b in {'xiaomi','redmi','poco'} else b if b!='samsung' else 'samsung_page'

def identity_confirmed(photo,product,sources,ev):
    b=product['brand'].strip().casefold()
    if b in {'xiaomi','redmi','poco','dreame'}:
        eligible={x['asset_key'] for x in ev.get('model_gallery_candidates',[]) if x.get('model_relation')=='model_confirmed'}
        return photo['asset_key'] in eligible|set(ev.get('model_gallery_assets',ev.get('exact_photo_assets',[]))) and photo['kind'] in {'product_gallery','official_model_visual'}
    if b=='electrolux':return any(x.get('asset_key')==photo['asset_key'] and x.get('eligible') for x in ev.get('gallery_inventory',[])) or photo['asset_key'] in ev.get('model_gallery_assets',[])
    if b=='lg':
        from .lg_identity import photo_tied_to_article
        return photo_tied_to_article(photo,sources)
    if b=='samsung':
        from .samsung_readiness import photo_verified
        return photo_verified(photo,sources,product['search_code'])
    if b=='hyperx':
        # Existing parser places only exact-variant images in product_gallery;
        # different layouts/color media are explicitly excluded/candidates.
        return photo['kind']=='product_gallery' and not photo.get('excluded_reason') and any(s['source_key']=='hyperx' and s['match_level']=='exact_variant' and not s['error'] for s in sources)
    if b=='apple':return photo['asset_key'] in ev.get('all_official_photo_assets',[]) or photo['asset_key'] in ev.get('exact_photo_assets',[]) and photo['kind']=='product_gallery'
    if b in {'jbl','razer','xbox','playstation'}:
        return (photo['asset_key'] in ev.get('all_official_photo_assets',[]) or photo['asset_key'] in ev.get('exact_photo_assets',[]) and photo['kind']=='product_gallery') and photo['kind']!='excluded'
    return False

def persist_measurement(database,product_id,photo,measurement):
    jobs.save_photo_metadata(database,product_id,photo['id'],photo['url'],width=measurement['width'],height=measurement['height'],size_bytes=measurement['size_bytes'],image_format=measurement['format'])
    ev=card_evidence.load(database,product_id,'photo_inventory') or {'entries':{}}
    stable_key=photo['source_key']+' / '+photo['asset_key']+' / '+photo['url']
    ev.get('invalid_entries',{}).pop(stable_key,None)
    ev['entries'][stable_key]={'url':photo['url'],'source_key':photo['source_key'],'asset_key':photo['asset_key'],'normalized_asset':normalized_asset(photo['url']),'role':role(photo),'verified_at':__import__('datetime').datetime.now(__import__('datetime').timezone.utc).isoformat(),**measurement}
    card_evidence.save(database,product_id,'photo_inventory',ev)

def enriched_photos(database,product_id,*,dedupe=True):
    photos=jobs.get_photo_candidates(database,product_id,include_excluded=True)
    proof=(card_evidence.load(database,product_id,'photo_inventory') or {}).get('entries',{})
    invalid_entries=(card_evidence.load(database,product_id,'photo_inventory') or {}).get('invalid_entries',{})
    product=jobs.get_product(database,product_id);sources=jobs.get_source_pages(database,product_id)
    ev=card_evidence.load(database,product_id,evidence_kind(product)) or {}
    for p in photos:
        if re.search(r'\*img\*|\{\{|\$\{|%7B%7B|\{(?:width|height)\}|%7B(?:width|height)%7D',p['url'],re.I):
            p['kind']='excluded';p['excluded_reason']='Template placeholder URL, not a published image asset'
        if re.search(r'\.(?:mp4|webm|mov|m3u8)(?:$|[?#])',p['url'],re.I):
            p['kind']='excluded';p['excluded_reason']='Video media, not a gallery image'
        invalid=invalid_entries.get(p['source_key']+' / '+p['asset_key']+' / '+p['url'])
        if invalid:
            p['kind']='excluded';p['excluded_reason']=invalid['reason'];p['byte_rejection']=invalid
        m=proof.get(p['source_key']+' / '+p['asset_key']+' / '+p['url'],{}) or next((x for x in proof.values() if x.get('source_key')==p['source_key'] and x.get('asset_key')==p['asset_key'] and x.get('url')==p['url']),{})
        if m.get('url')==p['url']:
            p.update(m)
            if m.get('verified_url') and m['verified_url']!=p['url']:
                p['published_rendition_url']=p['url'];p['url']=m['verified_url']
        p['identity_confirmed']=p['kind']!='excluded' and identity_confirmed(p,product,sources,ev)
        p['byte_verified']=bool(p.get('sha256') and p.get('verified_width'))
        p['role']=p.get('role') or role(p);p['normalized_asset']=normalized_asset(p['url'])
        p['role_label']=ROLE_LABELS.get(p['role'],'Роль не определена')
        p['model_relation']='confirmed' if p['identity_confirmed'] else 'unproven'
        meta=next((x for key in ('photos','model_gallery_candidates','gallery_inventory') for x in (ev.get(key) or []) if isinstance(x,dict) and x.get('asset_key')==p['asset_key']),{})
        p['variant_relation']=meta.get('relation') or meta.get('supplier_color_relation') or ('published asset identity' if p['identity_confirmed'] else 'unproven')
        p['official_color']=meta.get('official_color') or meta.get('color') or meta.get('options',{}).get('color','')
        p['source_url']=next((s['url'] for s in sources if s['source_key']==p['source_key']),'')
    if not dedupe:return photos
    groups=dedupe_groups(photos)
    result=[]
    for members in groups:
        best=max(members,key=lambda p:(bool(p['byte_verified']),(p.get('verified_width') or p.get('width') or 0)*(p.get('verified_height') or p.get('height') or 0),p.get('verified_bytes') or 0))
        best={**best,'selected':int(any(x['selected'] for x in members)),'aliases':[{'id':x['id'],'url':x['url'],'asset_key':x['asset_key']} for x in members if x['id']!=best['id']]}
        result.append(best)
    return result

def dedupe_groups(photos):
    """Rendition aliases and identical bytes are independent duplicate proofs."""
    parents=list(range(len(photos)));seen={}
    def root(i):
        while parents[i]!=i:
            parents[i]=parents[parents[i]];i=parents[i]
        return i
    for i,p in enumerate(photos):
        scope=(p['identity_confirmed'],p.get('official_color',''),p.get('variant_relation',''),p.get('excluded_reason',''))
        keys=[('asset',p['normalized_asset'])]
        if p.get('sha256'):keys.append(('sha256',p['sha256']))
        for key in keys:
            signature=(scope,key)
            if signature in seen:parents[root(i)]=root(seen[signature])
            else:seen[signature]=i
    groups={}
    for i,p in enumerate(photos):groups.setdefault(root(i),[]).append(p)
    return list(groups.values())

def complete(database,product_id,*,underlying=None,budget_seconds=180,clock=time.monotonic):
    """Bounded, resumable byte completion. Unchecked/failed assets stay visible."""
    end=clock()+budget_seconds;root=Path(database).parent
    product=jobs.get_product(database,product_id);sources=jobs.get_source_pages(database,product_id)
    ev=card_evidence.load(database,product_id,evidence_kind(product)) or {}
    results=[]
    measured_urls={}
    def journal(state,**fields):
        with (root/'gallery_timing.jsonl').open('a',encoding='utf8') as log:
            log.write(json.dumps({'product_id':product_id,'stage':'gallery_byte_verification','state':state,'timestamp':datetime.now(timezone.utc).isoformat(),'monotonic':clock(),**fields},ensure_ascii=False)+'\n')
    journal('start',budget_seconds=budget_seconds)
    pending=sorted(enriched_photos(database,product_id,dedupe=False),key=lambda p:not p['identity_confirmed'])
    for p in pending:
        if p['kind']=='excluded' or p['source_key'] not in photo_metadata.ALLOWED_BY_SOURCE:continue
        if p['byte_verified']:continue
        if clock()>=end:results.append({'url':p['url'],'state':'pending','reason':'bounded gallery phase expired; asset retained'});continue
        started=clock();journal('image_start',url=p['url'],source=p['source_key'])
        try:
            m=measured_urls.get((p['source_key'],p['url']))
            if m is None:
                target=published_origin(p['url'])
                try:m=photo_metadata.inspect_saved_photo(target,p['source_key'],root/photo_metadata.log_name(p['source_key']),underlying=underlying,full_verification=True,save_dir=root/'official_images')
                except ValueError:
                    if target==p['url']:raise
                    # Different explicitly published renderer host; its ordinary
                    # access policy still applies. Neither host stop is cleared.
                    target=p['url']
                    m=photo_metadata.inspect_saved_photo(target,p['source_key'],root/photo_metadata.log_name(p['source_key']),underlying=underlying,full_verification=True,save_dir=root/'official_images')
                m['verified_url']=target
            measured_urls[(p['source_key'],p['url'])]=m
            persist_measurement(database,product_id,p,m);results.append({'url':p['url'],'state':'verified','identity_confirmed':identity_confirmed(p,product,sources,ev),'sha256':m['sha256']})
            journal('image_end',url=p['url'],verified_url=m.get('verified_url',p['url']),seconds=clock()-started,sha256=m['sha256'])
        except Exception as exc:
            reason=str(exc);results.append({'url':p['url'],'state':'unverified','reason':reason})
            if any(s in reason for s in ('failed decoding verification','format/content-type mismatch','too small to be a product render')):
                evidence=card_evidence.load(database,product_id,'photo_inventory') or {'entries':{}}
                evidence.setdefault('invalid_entries',{})[p['source_key']+' / '+p['asset_key']+' / '+p['url']]={'reason':reason,'checked_at':datetime.now(timezone.utc).isoformat(),'cause':str(exc.__cause__) if exc.__cause__ else ''}
                card_evidence.save(database,product_id,'photo_inventory',evidence)
            journal('image_end',url=p['url'],seconds=clock()-started,exception=type(exc).__name__,reason=reason)
    state=card_evidence.load(database,product_id,'photo_inventory') or {'entries':{}}
    state['last_completion']={'budget_seconds':budget_seconds,'results':results};card_evidence.save(database,product_id,'photo_inventory',state)
    journal('end',verified=sum(r['state']=='verified' for r in results),pending=sum(r['state']=='pending' for r in results))
    return state
