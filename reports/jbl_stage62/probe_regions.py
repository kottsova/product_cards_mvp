from pathlib import Path
import json
from product_tool.adapters.policy_session import PolicyAwareSession
r=Path('reports/jbl_stage62');s=PolicyAwareSession(r/'other_regions_fetch.json',allowed_hosts=('dk.jbl.com','in.jbl.com','id.jbl.com','jbl.kz'));results=[]
for u in ['https://dk.jbl.com/JBLCHARGE5BLK.html','https://in.jbl.com/JBLCHARGE5BLK.html','https://id.jbl.com/en/JBLCHARGE5BLK.html','https://jbl.kz/','https://www.jbl.com/sitemap_index.xml']:
 try:
  z=s.get(u,timeout=10);item={'url':u,'final_url':z.url,'status':z.status_code,'marker':z.marker,'length':len(z.text)}
  if z.ok and len(z.text)>1000:
   file='other_'+str(len(results))+'.html';(r/file).write_text(z.text,encoding='utf-8');item['file']=file
  results.append(item)
 except Exception as e:results.append({'url':u,'error':str(e)[:150]})
 print(results[-1],flush=True)
(r/'other_regions.json').write_text(json.dumps(results,indent=2),encoding='utf-8')
