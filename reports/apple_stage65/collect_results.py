"""Collect the latest ordinary worker jobs; no adapter or source injection."""
from pathlib import Path
import json,hashlib
from product_tool import jobs,storage,apple_pipeline,card_evidence,discovery_trace
r=Path('reports/apple_stage65');p=r/'final_run.sqlite3';rows=[]
for product in storage.get_batch(p,'apple64')['products']:
 pid=product['id'];job=jobs.list_jobs(p,pid)[0];assert job['status']=='done'
 rows.append(dict(article=product['search_code'],job=job,sources=jobs.get_source_pages(p,pid),facts=jobs.get_facts(p,pid),resolved=jobs.get_resolved(p,pid),photos=jobs.get_photo_candidates(p,pid),documents=jobs.get_documents(p,pid),readiness=apple_pipeline.card_readiness(p,pid),events=jobs.list_events(p,job['id']),evidence=card_evidence.load(p,pid,'apple'),trace=discovery_trace.for_job(p,job['id'])))
dataset=Path('reports/apple_stage64/dataset_frozen.json');digest=hashlib.sha256(dataset.read_bytes()).hexdigest();assert digest=='8df1c4527b47f2c2103ff7fe70dc55e607dea50aa5cab20fb7ea6fcab5f41f81'
(r/'final_acceptance.json').write_text(json.dumps(dict(dataset_sha256=digest,pipeline='Latest ordinary run_once jobs on unchanged frozen dataset; category model registry, exact order overrides and verified official catalog fallback; no injected per-SKU source URLs',baseline=rows[0],results=rows[1:]),ensure_ascii=False,indent=2,default=str),encoding='utf-8')
print('Collected latest jobs:',[(x['article'],x['readiness']['confirmed_specs']) for x in rows])
