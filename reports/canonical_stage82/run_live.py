"""Sequential ordinary actual jobs; one persistent context per browser brand."""
import subprocess,json,sys
from pathlib import Path
R=Path(__file__).parent
plan=json.loads((R/'live_plan.json').read_text(encoding='utf8'))
for brand,ids in plan['selection'].items():
 result=subprocess.run([sys.executable,str(R/'live_batch.py'),'actual_live',brand,*map(str,ids)])
 if result.returncode:raise SystemExit(result.returncode)
