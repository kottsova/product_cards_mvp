"""Actual live gallery/manual supplement; stored live PDP supplies only identity."""
import sys,json,time,hashlib
from pathlib import Path
from types import SimpleNamespace
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from product_tool import jobs,card_evidence,readiness
from product_tool.fetch_history import latest_source_snapshot
from product_tool.adapters.hyperx import HyperXAdapter
from product_tool.census.public_browser import PublicBrowserSession
from product_tool.photo_metadata import inspect_saved_photo
R=Path(__file__).parent;db=R/'live_final.sqlite3'
rows=json.loads((R/'live_final.json').read_text(encoding='utf8'))['rows'];out={'origin':'actual live image/PDF/support supplement, not another PDP live-run','system_ca':True,'rows':[]}
b=PublicBrowserSession(allowed_hosts=('hyperx.com','supportcenter.hyperx.com','files.hyperx.com'),fetch_log_path=R/'hyperx_fetch_log.json',profile_dir=Path('data/hyperx_stage73_chrome_profile'),visible=True,resource_hosts=('prod-care-community-cdn.sprinklr.com','prod.cdata.app.sprinklr.com'),allow_readonly_graphql=True,readonly_graphql_paths=('/schema/community',),use_system_ca=True)
adapter=HyperXAdapter(discovery_enabled=True,browser_session=b,fetch_log_path=R/'hyperx_fetch_log.json',capture_dir=R/'captures')
try:
 b.start();base=b.binary_transport()
 class Capture:
  headers={}
  def get(self,url,**kwargs):
   response=base.get(url,**kwargs)
   if response.status_code==200:
    digest=hashlib.sha256(response.content).hexdigest();ct=response.headers.get('content-type','').split(';')[0];suffix={'image/png':'.png','image/jpeg':'.jpg','image/webp':'.webp'}.get(ct,'.bin');directory=R/'images';directory.mkdir(exist_ok=True);(directory/(digest+suffix)).write_bytes(response.content)
   return response
 transport=Capture()
 for row in rows:
  pid=row['product_id'];p=row['input'];ev=card_evidence.load(db,pid,'hyperx') or {};item={'id':row['id'],'product_id':pid,'photos':[]}
  for photo in jobs.get_photo_candidates(db,pid):
   if not photo['selected'] or photo['excluded_reason'] or photo['kind']!='product_gallery':continue
   record={'url':photo['url'],'asset_key':photo['asset_key'],'verified':False}
   try:
    metadata=inspect_saved_photo(photo['url'],'hyperx',R/'hyperx_fetch_log.json',underlying=transport)
    jobs.save_photo_metadata(db,pid,photo['id'],photo['url'],width=metadata['width'],height=metadata['height'],size_bytes=metadata['size_bytes'],image_format=metadata['format']);record.update(metadata,verified=True)
   except Exception as exc:record.update(error=str(exc),transport_error=base.last_error)
   item['photos'].append(record)
  ev['byte_verified_gallery']=item['photos']
  snapshot=latest_source_snapshot(db,pid,'hyperx')
  if snapshot and snapshot['content']:
   source=next(s for s in row['sources'] if s['source_key']=='hyperx');adapter._last_document=SimpleNamespace(url=source['url'],html=snapshot['content']);adapter._last_name=p['name'];adapter._last_category=p['category'];adapter.reports[p['article']]=ev
   documents,reason=adapter.find_documents(p['article'],deadline=time.monotonic()+90)
   jobs.save_documents(db,pid,'hyperx',documents);ev=adapter.reports[p['article']];item['manual_reason']=reason
  card_evidence.save(db,pid,'hyperx',ev)
  item.update(manual_status=ev.get('manual_status'),manuals=ev.get('manuals',[]),checks=ev.get('manual_checks',[]),technical=ev.get('manual_technical_limitations',[]),documents=jobs.get_documents(db,pid),readiness=readiness.card_readiness(db,pid))
  out['rows'].append(item);(R/'assets_actual.json').write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding='utf8')
  print(row['id'],'images',sum(i['verified'] for i in item['photos']), '/',len(item['photos']),'manual',item['manual_status'],'docs',len(item['documents']),item.get('technical'),flush=True)
finally:b.close();out['session_id']=b.session_id;out['contexts']=1;(R/'assets_actual.json').write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding='utf8')
