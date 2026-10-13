"""Actual live, bounded continuation of saved galleries; no discovery or manual IO."""
import sys,json,time,requests
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[2]));sys.stdout.reconfigure(encoding='utf8')
from product_tool import photo_inventory,storage,jobs
from product_tool.census.public_browser import IsolatedPublicBrowserSession
from product_tool.census.browser_contracts import BrowserBudget
R=Path(__file__).parent;phase,brand=sys.argv[1:3];root=R/phase;db=root/'batch.sqlite3'
inputs=json.loads((R/'dataset.json').read_text(encoding='utf8'))['rows']
rows=[r for r in inputs if r['brand']==brand and (not sys.argv[3:] or str(r['id']) in sys.argv[3:])]
session=None;http=None;events=[]
try:
 if brand in {'Razer','HyperX','Dreame','Electrolux'}:
  hosts={'Razer':('razer.com','razerzone.com'),'HyperX':('hyperx.com','cdn.shopify.com','files.hyperx.com','supportcenter.hyperx.com'),'Dreame':('dreametech.com','dreame.tech','cdn.shopify.com'),'Electrolux':('electrolux.co.uk','electrolux.ie','electrolux.se','electrolux.de','electrolux.pl','electrolux.com','electroluxgroup.eu','electrolux.bynder.com','electrolux-ui.com')}[brand]
  session=IsolatedPublicBrowserSession(allowed_hosts=hosts,profile_dir=Path('data')/(brand.casefold()+'_stage81_chrome_profile'),fetch_log_path=root/(brand.casefold()+'_fetch_log.json'),visible=True,use_system_ca=True,budget=BrowserBudget(deadline_seconds=40,operation_timeout_seconds=10))
  session.start();transport=session.binary_transport(max_bytes=8_000_000)
 else:http=requests.Session();transport=http
 for row in rows:
  assert (root/str(row['id'])/'result.json').exists(),'Cannot complete an unobserved product'
  for attempt in range(3):
   photos=photo_inventory.enriched_photos(db,row['id'])
   pending=[p for p in photos if p['kind']!='excluded' and p['identity_confirmed'] and not p['byte_verified']]
   if not pending:break
   started=time.monotonic();result=photo_inventory.complete(db,row['id'],underlying=transport,budget_seconds=180)
   event={'id':row['id'],'brand':brand,'attempt':attempt+1,'actual_live_image_requests':True,'pending_before':len(pending),'seconds':round(time.monotonic()-started,2),'results':result['last_completion']['results']}
   events.append(event);(root/(brand.casefold()+'_gallery_continuation.json')).write_text(json.dumps(events,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
   remaining=[p for p in photo_inventory.enriched_photos(db,row['id']) if p['kind']!='excluded' and p['identity_confirmed'] and not p['byte_verified']]
   print({k:v for k,v in event.items() if k!='results'},'pending_after',len(remaining),flush=True)
   if len(remaining)>=len(pending):break # No repeated requests against an unchanged access stop.
finally:
 if session:session.close()
 if http:http.close()
