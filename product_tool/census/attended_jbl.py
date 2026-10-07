"""Explicit ordinary attended capture of one official JBL PDP, shared capture pattern."""
import argparse,hashlib,json,re,time
from pathlib import Path
from urllib.parse import urlsplit
from .attended_support import looks_like_challenge
from ..adapters.jbl import official,parse_pdp

def capture(article,url,output,profile,*,playwright_factory=None):
 article=article.strip().upper();output=Path(output);profile=Path(profile)
 if not re.fullmatch(r'[A-Z0-9-]{5,50}',article) or not official(url):raise ValueError('Full article and an observed official HTTPS JBL PDP required')
 if output.resolve()==profile.resolve():raise ValueError('Separate browser profile and capture output required')
 if any(x in urlsplit(url).path.casefold() for x in ('account','checkout','cart','login')):raise ValueError('Product page required')
 if playwright_factory is None:
  from playwright.sync_api import sync_playwright
  playwright_factory=sync_playwright
 output.mkdir(parents=True,exist_ok=True);events=[];state={'stopped':False,'navigation':0,'resources':0}
 with playwright_factory() as pw:
  context=pw.chromium.launch_persistent_context(str(profile.resolve()),headless=False,viewport={'width':1440,'height':1000});page=context.pages[0] if context.pages else context.new_page()
  def route(request):
   req=request.request;state['resources']+=1
   if req.is_navigation_request():state['navigation']+=1
   if state['stopped'] or state['resources']>150 or state['navigation']>5 or not official(req.url):request.abort()
   else:request.continue_()
  def response(res):
   if res.request.is_navigation_request():
    events.append({'url':res.url,'status':res.status})
    if res.status in {401,403,429}:state['stopped']=True
  context.route('**/*',route);page.on('response',response);page.on('download',lambda d:d.cancel());context.on('page',lambda p:p.close() if p!=page else None)
  html='';notice=''
  try:
   page.goto(url,wait_until='domcontentloaded',timeout=30000);page.wait_for_timeout(1200);html=page.content()
   if looks_like_challenge(page.url,html):state['stopped']=True
  except Exception as exc:notice=type(exc).__name__
  final=page.url;doc,ev=parse_pdp(html,final,article);accepted=not state['stopped'] and events and events[-1]['status']==200 and doc.match_level in {'full_sku','model_confirmed'}
  result={'article':article,'flow':'ordinary visible attended capture','challenge_or_access_stop':state['stopped'],'accepted':bool(accepted),'events':events,'notice':notice,'identity':ev['identity']}
  if accepted:
   raw=html.encode('utf-8');name=article+'_attended.html';(output/name).write_bytes(raw)
   (output/(article+'.manifest.json')).write_text(json.dumps({'article':article,'records':[{'file':name,'sha256':hashlib.sha256(raw).hexdigest(),'status':200,'challenge':False,'final_url':final,'provider':'attended_browser'}]},indent=2),encoding='utf-8')
  (output/(article+'.capture_attempt.json')).write_text(json.dumps(result,indent=2),encoding='utf-8');context.close();return result

def main():
 parser=argparse.ArgumentParser();parser.add_argument('--article',required=True);parser.add_argument('--url',required=True);parser.add_argument('--output',type=Path,required=True);parser.add_argument('--profile',type=Path,required=True);args=parser.parse_args();print(json.dumps(capture(args.article,args.url,args.output,args.profile),ensure_ascii=True))
if __name__=='__main__':main()
