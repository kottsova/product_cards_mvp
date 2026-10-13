"""Serial live brand runs: shared ordinary job queue must never be raced."""
import sys,subprocess,json
from pathlib import Path
r=Path(__file__).parent;phase=sys.argv[1]
brands=['Samsung','LG','Apple','PlayStation','Xbox','Razer','HyperX','Xiaomi','Dreame','Electrolux']
results=[]
for brand in brands:
 print('BRAND_START',brand,flush=True)
 p=subprocess.run([sys.executable,str(r/'live_batch.py'),phase,brand])
 results.append({'brand':brand,'process_exit':p.returncode})
 (r/phase/'brand_processes.json').write_text(json.dumps(results,indent=2)+'\n',encoding='utf8')
 print('BRAND_END',brand,p.returncode,flush=True)
 if p.returncode:sys.exit(p.returncode)
