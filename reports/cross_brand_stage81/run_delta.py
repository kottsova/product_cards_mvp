"""Fresh actual live reruns after the last extraction changes; separate job DB."""
import subprocess,sys
from pathlib import Path
root=Path(__file__).parent
for brand in ('Apple','JBL'):
 print('DELTA_LIVE_START',brand,flush=True)
 result=subprocess.run([sys.executable,str(root/'live_batch.py'),'final_delta_live',brand])
 assert result.returncode==0,(brand,result.returncode)
 print('DELTA_LIVE_END',brand,flush=True)
result=subprocess.run([sys.executable,str(root/'live_batch.py'),'final_delta_live','Xiaomi','86','87'])
assert result.returncode==0,('Xiaomi',result.returncode)
