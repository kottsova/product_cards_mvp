"""Freeze the Stage 70 bytes and preserve its access history, without rewriting it."""
import hashlib,json
from pathlib import Path
from datetime import datetime,timezone
from product_tool.adapters import policy_fetch,access_stop
R=Path(__file__).parent;old=R.parent/'razer_stage70'
raw=(old/'frozen_inputs.json').read_bytes()
assert hashlib.sha256(raw).hexdigest()=='3165106f1f0ef283c7002d399f5096d4688c20463dd5137cc22f430aae9b08cd'
(R/'frozen_inputs.json').write_bytes(raw)
(R/'frozen_inputs.sha256').write_text(hashlib.sha256(raw).hexdigest(),encoding='utf8')
log=R/'razer_fetch_log.json'
if not log.exists():log.write_bytes((old/'razer_fetch_log.json').read_bytes())
history=policy_fetch.read_log(log);now=datetime.now(timezone.utc)
out={'at':now.isoformat(),'baseline_commit':'61fc1e522a6d336c9509dd0334aeedeb55e2cb05','dataset_sha256':hashlib.sha256(raw).hexdigest(),'history_entries':len(history),'active_stops':access_stop.active_stops(history,now=now),'historical_stops':[x for x in history if access_stop.stop_reason(x)]}
(R/'initial_lifecycle.json').write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding='utf8')
print(json.dumps({k:v for k,v in out.items() if k!='historical_stops'},ensure_ascii=False))
