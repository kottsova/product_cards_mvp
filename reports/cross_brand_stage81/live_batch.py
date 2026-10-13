"""Frozen mixed inputs through ordinary production jobs; no prior PDP/capture injection."""
import sys,json,hashlib,time,sqlite3,os,traceback
from pathlib import Path
from datetime import datetime,timezone
from contextlib import ExitStack
sys.path.insert(0,str(Path(__file__).resolve().parents[2]));sys.stdout.reconfigure(encoding='utf8')
from product_tool import storage,jobs,worker,readiness,card_evidence,discovery_trace,attribute_projection,photo_inventory
from product_tool.census.public_browser import PublicBrowserSession,IsolatedPublicBrowserSession
from product_tool.census.browser_contracts import BrowserBudget
from product_tool.adapters.jbl import JBLAdapter
from product_tool.adapters.apple import AppleAdapter
from product_tool.adapters.xiaomi import XiaomiAdapter
from product_tool.adapters.dreame import DreameAdapter
from product_tool.adapters.razer import RazerAdapter
from product_tool.adapters.hyperx import HyperXAdapter
from product_tool.adapters.electrolux import ElectroluxAdapter
from product_tool.adapters.playstation import PlayStationAdapter
from product_tool.adapters.xbox import XboxAdapter
R=Path(__file__).parent;phase=sys.argv[1];brand=sys.argv[2]
raw=(R/'dataset.json').read_bytes();sha=hashlib.sha256(raw).hexdigest();assert sha==(R/'dataset.sha256').read_text().strip()
rows=[x for x in json.loads(raw)['rows'] if x['brand']==brand and (not sys.argv[3:] or str(x['id']) in sys.argv[3:])]
assert rows
out=R/phase;out.mkdir(exist_ok=True);db=out/'batch.sqlite3';jobs.initialize(db);discovery_trace.initialize(db)
with storage._connection(db) as c:
 c.execute('INSERT OR IGNORE INTO batches VALUES (?,?,?,?,?)',('cb81','Stage 81 frozen mixed batch','Products','{}',storage._now()))
 for p in json.loads(raw)['rows']:
  original={**p['original_input'],'requested_region':p['region']}
  config={**p['input_configuration']}
  if p['region']:config['region']=p['region']
  if p['input_color']:config['color']=p['input_color']
  c.execute("INSERT OR IGNORE INTO products (id,batch_id,row_number,name,brand,search_code,alternate_code,category,needs_confirmation,issues_json,original_values_json,identity_json) VALUES (?,'cb81',?,?,?,?, '',?,0,'[]',?,?)",(p['id'],p['id'],p['name'],p['dispatch_brand'],p['article'],p['category'],json.dumps(original,ensure_ascii=False),json.dumps({'input_configuration':config},ensure_ascii=False)))
log=out/(brand.casefold()+'_fetch_log.json');capture=out/(brand.casefold()+'_captures');capture.mkdir(exist_ok=True)
kwargs={};b=None;a=None
if brand in {'HyperX','Razer','Dreame','Electrolux'}:
 hosts={'HyperX':('hyperx.com','supportcenter.hyperx.com','files.hyperx.com'),'Razer':('razer.com','razerzone.com'),'Dreame':('dreametech.com','dreame.tech','cdn.shopify.com'),'Electrolux':('electrolux.co.uk','electrolux.ie','electrolux.se','electrolux.de','electrolux.pl','electrolux.com','electroluxgroup.eu','electrolux.bynder.com','electrolux-ui.com')}[brand]
 extra={'resource_hosts':('prod-care-community-cdn.sprinklr.com','prod.cdata.app.sprinklr.com'),'allow_readonly_graphql':True,'readonly_graphql_paths':('/schema/community',)} if brand=='HyperX' else {}
 cls=IsolatedPublicBrowserSession if brand=='Electrolux' else PublicBrowserSession
 b=cls(allowed_hosts=hosts,fetch_log_path=log,profile_dir=Path('data')/(brand.casefold()+'_stage81_chrome_profile'),visible=True,use_system_ca=True,budget=BrowserBudget(deadline_seconds=40,operation_timeout_seconds=10),**extra)
 a={'HyperX':lambda:HyperXAdapter(discovery_enabled=True,browser_session=b,fetch_log_path=log,capture_dir=capture),'Razer':lambda:RazerAdapter(browser_session=b,fetch_log_path=log,capture_dir=capture),'Dreame':lambda:DreameAdapter(browser_session=b,fetch_log_path=log,capture_dir=capture,manuals_enabled=False),'Electrolux':lambda:ElectroluxAdapter(browser_session=b,fetch_log_path=log,capture_dir=capture)}[brand]()
else:
 factories={'JBL':lambda:JBLAdapter(fetch_log_path=log,capture_dir=capture),'Apple':lambda:AppleAdapter(fetch_log_path=log,manuals_enabled=False),'Xiaomi':lambda:XiaomiAdapter(fetch_log_path=log,capture_dir=capture,manuals_enabled=False),'PlayStation':lambda:PlayStationAdapter(fetch_log_path=log),'Xbox':lambda:XboxAdapter(fetch_log_path=log)}
 if brand in factories:a=factories[brand]()
if a:kwargs[brand.casefold()+'_adapter_factory']=lambda:a
families={'Samsung':'samsung_page','LG':'lg','PlayStation':'playstation'}
summ={'phase':phase,'brand':brand,'frozen_sha256':sha,'started_at':datetime.now(timezone.utc).isoformat(),'ordinary_worker':True,'stages':[1,2,3,4],'transport':'actual live; fresh report DB/log and no prior PDP replay; browser context reused within brand when required','rows':[]}
save_document=jobs.save_source_document
def observed_save(database,pid,document,**options):
 d=out/str(pid)/'raw_sources';d.mkdir(parents=True,exist_ok=True)
 payload={'source':document.source_key,'url':document.url,'found_model':document.found_model,'match_level':document.match_level,'error':document.error,'raw_specs':[{'section':x.section,'subsection':'','label':x.name,'value':x.value,'value_cell':x.value_cell} for x in document.attributes],'photos':[vars(x) for x in document.photo_candidates],'html_sha256':hashlib.sha256(document.html.encode()).hexdigest(),'observation':'returned live SourceDocument; discovery/transport trace determines cache vs fresh response'}
 (d/(document.source_key+'.json')).write_text(json.dumps(payload,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
 if document.html:(d/(document.source_key+'.html')).write_text(document.html,encoding='utf8')
 return save_document(database,pid,document,**options)
jobs.save_source_document=observed_save
try:
 if b:b.start()
 for p in rows:
  dest=out/str(p['id']);dest.mkdir(exist_ok=True)
  assert not (dest/'result.json').exists(),'Do not overwrite earlier observations'
  if a and hasattr(a,'capture_dir'):a.capture_dir=dest/'captures';a.capture_dir.mkdir(exist_ok=True)
  start=time.monotonic();jid=jobs.enqueue(db,p['id'],[1,2,3,4]);worker.run_once(db,**kwargs)
  if phase.startswith('final'):
   transport=a.photo_transport() if a and hasattr(a,'photo_transport') else b.binary_transport(max_bytes=8_000_000) if b else None
   photo_inventory.complete(db,p['id'],underlying=transport,budget_seconds=180)
  ev=card_evidence.load(db,p['id'],families.get(brand,brand.casefold())) or {}
  x={'input':p,'observed_at':datetime.now(timezone.utc).isoformat(),'seconds':round(time.monotonic()-start,2),'job':jobs.list_jobs(db,p['id'])[0],'sources':jobs.get_source_pages(db,p['id']),'facts':jobs.get_facts(db,p['id']),'resolved':jobs.get_resolved(db,p['id']),'canonical_output':attribute_projection.final_attribute_rows(db,p['id']),'photos':jobs.get_photo_candidates(db,p['id'],include_excluded=True),'all_official_gallery':photo_inventory.enriched_photos(db,p['id']),'photo_evidence':card_evidence.load(db,p['id'],'photo_inventory'),'documents':jobs.get_documents(db,p['id']),'evidence':ev,'readiness':readiness.card_readiness(db,p['id'],manuals_required=False),'readiness_with_documents':readiness.card_readiness(db,p['id']),'trace':discovery_trace.for_job(db,jid)}
  (dest/'result.json').write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
  item={'id':p['id'],'brand':brand,'model':p['model'],'category':p['category'],'seconds':x['seconds'],'job':x['job']['status'],'source_urls':[s['url'] for s in x['sources'] if s['url'] and not s['error']],'facts':len(x['facts']),'canonical':len(x['canonical_output']),'photos':len(x['photos']),'selected':sum(bool(ph['selected']) for ph in x['photos']),'documents_fetched':len(x['documents']),'readiness':x['readiness']['verdict']}
  summ['rows'].append(item);(out/(brand.casefold()+'_summary.json')).write_text(json.dumps(summ,ensure_ascii=False,indent=2)+'\n',encoding='utf8');print(item,flush=True)
finally:
 jobs.save_source_document=save_document
 if b:b.close()
 if a and hasattr(a,'close'):a.close()
 summ['finished_at']=datetime.now(timezone.utc).isoformat();summ['context_closed']=not b or b.context is None
 (out/(brand.casefold()+'_summary.json')).write_text(json.dumps(summ,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
assert sha==hashlib.sha256((R/'dataset.json').read_bytes()).hexdigest()
