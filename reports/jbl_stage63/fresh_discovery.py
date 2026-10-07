from pathlib import Path
import json,shutil,time
from product_tool.adapters.jbl import JBLAdapter
r=Path('reports/jbl_stage63');root=r/'fresh_discovery';root.mkdir(exist_ok=True);log=root/'jbl_fetch_log.json';previous=Path('reports/jbl_stage62/jbl_fetch_log.json')
if not log.exists() and previous.exists():shutil.copyfile(previous,log)
rows=[]
for sku,name in [('JBLT520BTBLKEU','JBL Tune 520BT'),('JBLT520BTWHTEU','JBL Tune 520BT'),('JBLXTREME4BLUEP','JBL Xtreme 4'),('JBLBAR500PROBLKEP','JBL Bar 500')]:
 trace=[];a=JBLAdapter(fetch_log_path=log,capture_dir=root/'jbl_captures',trace_callback=trace.append);start=time.monotonic();d=a.find_source(sku,name=name,deadline=start+65);e=a.reports[sku];x={'sku':sku,'duration':round(time.monotonic()-start,2),'source_url':d.url,'match_level':d.match_level,'specs':len(d.attributes),'photo_assets':e['exact_photo_assets'],'identity':e['identity'],'trace':trace};rows.append(x);(r/'fresh_discovery.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2),encoding='utf-8');print(sku,d.match_level,len(d.attributes),len(e['exact_photo_assets']),d.url,flush=True)
