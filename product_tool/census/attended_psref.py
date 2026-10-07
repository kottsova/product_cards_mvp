"""Explicit PSREF capture using the existing attended support capture pattern.

Observe the official frontend in a visible ordinary browser, then import its
original responses offline. Never interact with challenges or manufacture auth.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import re
import time
from pathlib import Path
from urllib.parse import urlsplit
from .attended_support import looks_like_challenge

PATHS=('/api/model/Info/GetInfoByKey','/api/model/Info/SpecData','/api/product/Photo/','/api/product/Info/ShowDocumentations')

def capture(article, output_dir, profile_dir, *, playwright_factory=None, max_wait_seconds=20, announce=print):
    article=article.strip().upper()
    if not re.fullmatch(r'[A-Z0-9]{8,12}',article):raise ValueError('A complete Lenovo MTM/part number is required')
    output_dir=Path(output_dir);profile_dir=Path(profile_dir)
    if output_dir.resolve()==profile_dir.resolve():raise ValueError('Capture and browser profile must differ')
    output_dir.mkdir(parents=True,exist_ok=True)
    if playwright_factory is None:
        from playwright.sync_api import sync_playwright
        playwright_factory=sync_playwright
    url=f'https://psref.lenovo.com/Detail/Model?M={article}'
    records=[];state={'resources':0,'navigations':0,'stopped':False}
    with playwright_factory() as pw:
        context=pw.chromium.launch_persistent_context(str(profile_dir),headless=False,accept_downloads=False,viewport={'width':1400,'height':900})
        page=context.pages[0] if context.pages else context.new_page()
        def route_request(route):
            parsed=urlsplit(route.request.url)
            if state['stopped'] or parsed.scheme!='https' or parsed.hostname not in {'psref.lenovo.com','psrefstuff.lenovo.com'} or state['resources']>=200:
                route.abort();return
            if route.request.is_navigation_request():
                state['navigations']+=1
                if state['navigations']>4:state['stopped']=True;route.abort();return
            state['resources']+=1;route.continue_()
        def finished(request):
            parsed=urlsplit(request.url)
            if parsed.hostname=='psref.lenovo.com' and '/api/' in parsed.path:
                response=request.response()
                if response and response.status in {401,403,429}:state['stopped']=True
            if parsed.hostname!='psref.lenovo.com' or not any(parsed.path.startswith(p) for p in PATHS):return
            try:
                response=request.response()
                if response is None:return
                record={'url':response.url,'status':response.status,'authorization_present':bool(request.headers.get('authorization'))}
                if response.status in {401,403,429}:state['stopped']=True
                body=response.body()
                if len(body)>2_000_000 or len(records)>=12:record['reason']='response_budget_exhausted'
                else:
                    digest=hashlib.sha256(body).hexdigest();name=digest+'.json';(output_dir/name).write_bytes(body)
                    record.update(file=name,sha256=digest,content_type=response.headers.get('content-type',''))
                records.append(record)
            except Exception as exc:records.append({'url':request.url,'error':type(exc).__name__})
        context.route('**/*',route_request);page.on('requestfinished',finished)
        page.on('download',lambda download:download.cancel())
        context.on('page',lambda opened:opened.close() if opened!=page else None)
        started=time.monotonic();notice=''
        announce(f'Visible ordinary browser: official PSREF {article}; no automated challenge interaction.')
        try:
            page.goto(url,wait_until='domcontentloaded',timeout=30_000)
            while time.monotonic()-started<max_wait_seconds:
                page.wait_for_timeout(500)
                if state['stopped'] or looks_like_challenge(page.url,page.content()):state['stopped']=True;break
                if all(any(p in r['url'] and r.get('file') for r in records) for p in PATHS):break
            page.wait_for_timeout(500)
        except Exception as exc:notice=type(exc).__name__
        manifest={'article':article,'entry_url':url,'final_url':page.url,'captured_at':time.time(),'flow':'attended passive frontend capture',
                  'challenge':state['stopped'],'records':records,'notice':notice,'resources':state['resources']}
        if not state['stopped']:
            (output_dir/f'{article}.html').write_text(page.content(),encoding='utf-8');manifest['dom_file']=f'{article}.html'
        (output_dir/f'{article}.manifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
        context.close()
    return manifest

def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--article',required=True);parser.add_argument('--output',type=Path,required=True);parser.add_argument('--profile',type=Path,required=True)
    args=parser.parse_args();result=capture(args.article,args.output,args.profile);print(json.dumps({'article':result['article'],'challenge':result['challenge'],'records':len(result['records'])}))

if __name__=='__main__':main()
