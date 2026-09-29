"""Bounded all-source structural sampling; no catalog model queries or browser code."""
from pathlib import Path
from urllib.parse import urlsplit,urljoin
import hashlib
import json
import time
from .structural_inventory_v8 import ROOT,OUTPUT,read,write,inventory,old_endpoints,snapshot_cache
from .structural_contracts_v8 import inspect_structure,LAYERS,cluster_profiles,digest
from .endpoint_probe import AccessProbe,ProbePolicy
from .models import EndpointCapability
from .search_routes import safe_url
from .search_snapshots import sanitized_url

MAX_HTTP=500
MAX_HOST_HTTP=8
MAX_PROFILE_HTTP=5

def protected(e):
    return e.get('http_status') in {403,429} or e.get('protection_status') in {'challenge_detected','captcha_detected','challenge_confirmed'} or e.get('access_status') in {'captcha_or_blocked','rate_limited'}

def in_scope(url,record):
    p=urlsplit(url);base=urlsplit(record['official_domain'])
    return p.hostname==base.hostname and (not base.path.rstrip('/') or p.path.rstrip('/')==base.path.rstrip('/') or p.path.startswith(base.path.rstrip('/')+'/'))

class Sampler:
    def __init__(self,cache,history,*,live=False,probe=None):
        self.cache=cache;self.history=history;self.live=live
        self.probe=probe or AccessProbe(policy=ProbePolicy(timeout_seconds=6,max_bytes=700_000,min_interval_seconds=1.5))
        self.attempts=read(OUTPUT/'http_attempts.json') if (OUTPUT/'http_attempts.json').exists() else []
        self.paused={urlsplit(e.get('final_url',e.get('url',''))).hostname for e in history if e.get('access_method','http')=='http' and protected(e)}
        self.paused.update(urlsplit(e.get('final_url',e.get('url',''))).hostname for e in cache.values() if protected(e))
        self.used={pid:sum(a['profile_id']==pid for a in self.attempts) for pid in {a['profile_id'] for a in self.attempts}};self.started={}
    def fetch(self,seed,record):
        url=seed['url'];pid=record['profile_id'];hosts=tuple(record['allowed_hosts'])
        if url in self.cache:return self.cache[url]
        if not self.live:raise RuntimeError('missing_offline_snapshot')
        if record.get('source_family')=='sulpak' and seed['kind'] not in {'homepage','support'}:raise RuntimeError('LG_appliance_scope_not_proven_for_dealer_sample')
        deadline=self.started.setdefault(pid,time.monotonic()+35)
        def guard(target):
            host=urlsplit(target).hostname
            if not safe_url(target,hosts):raise RuntimeError('unapproved_redirect_host')
            if host in self.paused:raise RuntimeError('HTTP_host_protection_pause')
            if len(self.attempts)>=MAX_HTTP or sum(urlsplit(a['url']).hostname==host for a in self.attempts)>=MAX_HOST_HTTP or self.used.get(pid,0)>=MAX_PROFILE_HTTP or time.monotonic()>=deadline:raise RuntimeError('bounded_sampling_limit')
            self.used[pid]=self.used.get(pid,0)+1
            self.attempts.append({'url':sanitized_url(target),'profile_id':pid,'access_method':'http','sample_kind':seed['kind'],'provenance':seed['provenance']})
            write(OUTPUT/'http_attempts.json',self.attempts)
            return max(.001,deadline-time.monotonic())
        cap=EndpointCapability.SUPPORT_PAGE if seed['kind']=='support' else EndpointCapability.PRODUCT_PAGE if seed['kind']=='product' else EndpointCapability.HOMEPAGE
        response=self.probe.probe(url,allowed_hosts=hosts,capability=cap,sample_type=seed['kind'],request_guard=guard,deadline=deadline)
        meta=response.to_dict()
        # Do not persist arbitrary headers, cookies, response body or diagnostic errors.
        data={k:meta[k] for k in ['url','final_url','http_status','access_status','protection_status','javascript_required','checked_at','redirect_chain']}
        if protected(data):self.paused.add(urlsplit(response.final_url or url).hostname)
        data.update(provenance=seed['provenance'],origin='stage8_http',snapshot_ref=None)
        if response.http_status==200 and not protected(data):
            data['structure']=inspect_structure(response.diagnostic_text,response.final_url,hosts)
        else:data['structure']=None
        self.cache[url]=data
        write(OUTPUT/'structural_cache.json',{u:v for u,v in self.cache.items() if v['origin']=='stage8_http'})
        return data


def profile(record,sampler):
    p=dict(record);p.pop('sample_seeds',None)
    p.update(access_method='http',production_ready=False,review_notes=[],samples=[],sample_homepage=None,sample_category_page=None,sample_product_page=None,sample_support_page=None)
    history=[e for e in sampler.history if in_scope(e.get('url',''),record)]
    candidates=[];seen=set();errors=[]
    def add(item,kind,provenance):
        if not item:return
        key=item['url']
        if key not in seen:
            seen.add(key);p['samples'].append({'url':sanitized_url(key),'final_url':sanitized_url(item.get('final_url',key)),'kind':kind,'provenance':provenance,'origin':item['origin'],'snapshot_ref':item.get('snapshot_ref'),'access_status':item.get('access_status'),'protection_status':item.get('protection_status'),'checked_at':item.get('checked_at'),'redirect_chain':[sanitized_url(u) for u in item.get('redirect_chain',[])],'javascript_required':item.get('javascript_required'),'structure':item.get('structure')})
        struct=item.get('structure')
        if not struct:return
        if kind=='homepage' and not p['sample_homepage']:p['sample_homepage']=key
        if kind=='category' and not p['sample_category_page']:p['sample_category_page']=key
        if kind=='support' and not p['sample_support_page']:p['sample_support_page']=key
        canonical=lambda u:(urlsplit(u).hostname,urlsplit(u).path.rstrip('/'))
        current_product=any(l['provenance'].get('method')=='JSON-LD_Product.url' and canonical(l['url'])==canonical(item.get('final_url',key)) for l in struct['links'])
        if (struct['is_product_page'] or current_product) and not p['sample_product_page']:p['sample_product_page']=key
        candidates.extend(struct['links'])
    for item in list(sampler.cache.values()):
        if in_scope(item['url'],record):
            struct=item.get('structure')
            kind='product' if struct and struct['is_product_page'] else 'support' if '/support' in urlsplit(item['url']).path else 'homepage' if item['url'].rstrip('/')==record['official_domain'].rstrip('/') else 'category'
            add(item,kind,item['provenance'])
    for seed in record['sample_seeds']:
        if p['sample_homepage'] or p['sample_product_page']:break
        try:add(sampler.fetch(seed,record),seed['kind'],seed['provenance'])
        except RuntimeError as exc:errors.append(str(exc));break
    # Bound each sample role. Only discovered first-party URLs can be requested.
    for kind,field in [('category','sample_category_page'),('product','sample_product_page'),('support','sample_support_page')]:
        if p[field]:continue
        options=[l for l in candidates if l['kind']==kind and l['url'] not in seen and safe_url(l['url'],tuple(record['allowed_hosts']))]
        for seed in options[:2 if kind=='product' else 1]:
            try:
                add(sampler.fetch(seed,record),kind,seed['provenance'])
                if p[field]:break
            except RuntimeError as exc:errors.append(str(exc));break
    # Never infer structure from platform/JS-only/protection summaries.
    sample=next((s for s in p['samples'] if s['url']==p['sample_product_page']),None)
    struct=sample['structure'] if sample else None
    p['layers']={}
    for layer in LAYERS:
        source=sample
        if layer=='discovery':source=next((s for s in p['samples'] if s.get('structure') and s['structure']['observed']['discovery']),sample)
        if layer=='documents':source=next((s for s in p['samples'] if s['kind']=='support' and s.get('structure') and s['structure']['observed']['documents']),sample)
        obj=source.get('structure') if source else None
        observed=bool(obj and obj['observed'][layer])
        fixture=None
        if observed:
            fixture='fixtures/'+obj['content_sha256']+'.json'
            (OUTPUT/'fixtures').mkdir(exist_ok=True)
            write(OUTPUT/fixture,{k:v for k,v in obj.items() if k!='links'})
        p['layers'][layer]={'observed':observed,'contract':obj['contracts'][layer] if observed else None,'signature':obj['signatures'][layer] if observed else None,'fixture':fixture,'contract_reviewed':False,'status':'custom_adapter_candidate' if observed else 'structure_partial','evidence_url':source['url'] if observed else None,'limitation':'Single sample; required-field stability and variants need fixture review before shared classification.' if observed else 'Not observed in bounded accessible evidence; no inferred contract.'}
    successful=[s for s in p['samples'] if s.get('structure')]
    host=urlsplit(record['official_domain']).hostname
    if struct:
        status='adapter_profile_complete' if all(p['layers'][l]['observed'] for l in LAYERS) else 'structure_partial'
    elif host in sampler.paused:status='http_blocked'
    elif any(s.get('javascript_required') for s in p['samples']) or any(e.get('javascript_required') for e in history):status='javascript_only'
    elif successful:status='product_page_not_found'
    else:status='manual_review_required'
    p.update(completeness_status=status,cms_fingerprint=[c for s in successful for c in s['structure']['cms_fingerprint']],javascript_dependency='observed' if any(s.get('javascript_required') for s in p['samples']) else 'unknown' if not successful else 'not_required_for_observed_contracts',locale_behavior={'configured_locale':record['locale'],'observed_contracts':sorted({s['structure']['contracts']['discovery']['locale_contract'] for s in successful})},redirect_behavior=[s['redirect_chain'] for s in p['samples'] if s['redirect_chain']],pagination_behavior=sorted({x for s in successful for x in s['structure']['contracts']['discovery']['pagination']}),last_checked_at=max([str(s.get('checked_at') or '') for s in p['samples']]+[str(e.get('checked_at') or '') for e in history]+['']),access_status='direct_access' if successful else 'blocked' if host in sampler.paused else 'unavailable_or_unobserved',protection_status='http_host_paused' if host in sampler.paused else 'no_confirmed_protection_in_sampled_HTTP',review_notes=errors+(['No reproducible product page obtained within bounded sampling.'] if not struct else [])+(['Sanitized historical snapshots omit media/embedded state; unobserved layers remain partial.'] if any(s['structure'].get('sanitized_snapshot_limitations') for s in successful) else []),next_action='Review missing layer contracts or verified first-party discovery provenance; no production activation.',history_evidence=[{'artifact':e.get('artifact'),'url':sanitized_url(e.get('url','')),'access_status':e.get('access_status'),'protection_status':e.get('protection_status'),'checked_at':e.get('checked_at')} for e in history])
    if not p['sample_support_page']:p['support_status']='support_structure_not_found'
    else:p['support_status']='observed' if p['layers']['documents']['observed'] else 'structure_partial'
    # Raw page text/product values never enter profiles or structural fixtures.
    for s in p['samples']:
        if s.get('structure'):
            s['content_sha256']=s['structure']['content_sha256'];s['structural_signatures']=s['structure']['signatures']
        s.pop('structure',None)
    return p


def execute(live=False,rebuild_offline=False):
    if live and rebuild_offline:raise ValueError('offline rebuild cannot use network')
    records,labels,families,missing,totals=inventory()
    write(OUTPUT/'inventory.json',{'records':records,'missing_verified_family_metadata':missing,'catalog':totals})
    cache=snapshot_cache(records)
    if (OUTPUT/'structural_cache.json').exists():cache.update(read(OUTPUT/'structural_cache.json'))
    # Old structural projections did not scope hreflang to document anchors.
    # They cannot establish document language. Correct them offline, never refetch.
    for item in cache.values():
        obj=item.get('structure')
        if not obj or obj.get('fixture_version',1)>=2:continue
        docs=obj['contracts']['documents']
        docs['link_schema']=[value for value in docs['link_schema'] if value!='a[hreflang]']
        docs['language_contract']='unknown_do_not_infer_from_locale'
        obj['observed']['documents']=bool(docs['link_schema'])
        identity=obj['contracts']['identity'];discovery=obj['contracts']['discovery']
        obj['signatures']['documents']=digest({'contract':docs,'identity_semantics':identity['model_semantics'],'variant_contract':identity['variant_fields'],'pagination':discovery['pagination'],'locale':discovery['locale_contract']})
        obj['fixture_version']=2
    sampler=Sampler(cache,old_endpoints(),live=live)
    previous=read(OUTPUT/'profiles_checkpoint.json') if (OUTPUT/'profiles_checkpoint.json').exists() else {}
    saved={} if rebuild_offline else previous
    for i,record in enumerate(records):
        if record['profile_id'] in saved:continue
        saved[record['profile_id']]=profile(record,sampler)
        if rebuild_offline and record['profile_id'] in previous:
            saved[record['profile_id']]['observed_sampling_stop_notes']=previous[record['profile_id']]['review_notes']
        write(OUTPUT/'profiles_checkpoint.json',saved)
        print(json.dumps({'completed':i+1,'total':len(records),'profile':record['profile_id'],'status':saved[record['profile_id']]['completeness_status'],'HTTP':len(sampler.attempts)}),flush=True)
    profiles=list(saved.values());clusters=cluster_profiles(profiles)
    write(OUTPUT/'adapter_profiles.v1.json',{'schema_version':1,'production_ready':False,'profiles':profiles})
    write(OUTPUT/'adapter_clusters.json',clusters)
    write(OUTPUT/'run_summary.json',{'new_http_requests':len(sampler.attempts),'limits':{'aggregate':MAX_HTTP,'host':MAX_HOST_HTTP,'profile':MAX_PROFILE_HTTP,'bytes':700000,'seconds_per_profile':35},'reused_snapshot_count':len({(s['snapshot_ref']['artifact'],s['snapshot_ref']['snapshot_id']) for p in profiles for s in p['samples'] if s.get('snapshot_ref')}),'browser_runs':0,'missing_verified_family_metadata':missing})
    return profiles

if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser();parser.add_argument('--live',action='store_true');parser.add_argument('--rebuild-offline',action='store_true');args=parser.parse_args();execute(args.live,args.rebuild_offline)
