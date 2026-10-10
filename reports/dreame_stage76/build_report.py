"""Evidence-based audit summary; research routes never become worker seeds."""
from pathlib import Path
import json,hashlib,sys
R=Path(__file__).parent
sys.path.insert(0,str(R.resolve().parents[1]))
def read(p):return json.loads((R/p).read_text(encoding='utf8'))
def save(p,x):(R/p).write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n',encoding='utf8')

paths=['l60-ultra','l10s-pro-gen-2','d30-ultra','dreame-x50-ultra-complete','h14-pro','h13-pro','dreame-h15-pro-heat','z30','h12-dual','x40-master']
manuals=['','','','x50-ultra-x50-ultra-complete-user-manual','h14-pro-user-manual','h13-pro-user-manual','h15-pro-heat','z30-user-manual','h12-dual-user-manual','x40-master-user-manual-1']
data=read('dataset.json')['rows'];first=read('first_pass/results.json')['rows'];final=read('final_live/results.json')['rows']
research=[]
for p,slug,manual in zip(data,paths,manuals):
    research.append({'id':p['id'],'model':p['model'],'pdp':'https://global.dreametech.com/products/'+slug,'provenance':'published official navigation followed via web research; NOT run_once discovery and NOT raw native DOM','manual_page':'https://global.dreametech.com/pages/'+manual if manual else '', 'manual_research_status':'Проверена' if p['id']==9 else 'Не проверена' if manual else 'Проверена, не найдена','manual_search_scope':'bounded official manual inventory only; empty is not proof of global absence','worker_source':False})
save('official_research_inventory.json',{'observation':'separate web research, no worker ingestion','rows':research})
manual=read('manual_research/result.json')
import pymupdf
from product_tool.adapters.dreame import manual_assessment
with pymupdf.open(R/'manual_research/H12_Dual_RU.pdf') as pdf:pages=[x.get_text() for x in pdf]
check,headings=manual_assessment(pages,['Dreame H12 Dual','H12 Dual']);assert check['accepted']
manual['dreame_assessment_after']=check;manual['guide_headings_after']=headings;save('manual_research/result.json',manual)
rows=[]
for a,b,src in zip(first,final,research):
    assert a['id']==b['id']==src['id']
    r=b['readiness'];ev=b['evidence'];assert r['confirmed_specs']==0 and not ev['live_success'] and not b['photos'] and not r['conflicts']
    assert 'manual_unverified' not in r['blocking_gaps'] and 'configuration_missing' not in r['blocking_gaps']
    rows.append({'id':b['id'],'model':b['input']['model'],'category':b['input']['category'],'research_pdp':src['pdp'],'worker_pdp':ev.get('pdp_url',''),'first_live_success':a['evidence']['live_success'],'final_live_success':ev['live_success'],'confirmed_specs':r['confirmed_specs'],'confirmed_photos':0,'manual_worker':r['manual_status'],'identity':ev['identity']['model_relation'],'configuration':ev['input_configuration'],'job_status':b['job']['status'],'readiness':r['verdict'],'blocking_gaps':r['blocking_gaps'],'root_cause':'Published official inventory unavailable through native transport: existing 429 cooldown; external fallback guard also stops. No trusted dealer URL.'})
summary={'dataset_sha256':(R/'dataset.sha256').read_text().strip(),'dataset_unchanged':hashlib.sha256((R/'dataset.json').read_bytes()).hexdigest()==(R/'dataset.sha256').read_text().strip(),'worker_rows_processed':10,'first_official_live_success':0,'final_official_live_success':0,'ready':0,'confirmed_specs':0,'byte_verified_worker_photos':0,'worker_manuals_checked':0,'replay_rows_substituted':0,'separate_manual_research_verified':1,'offline_contract_tests':21,'new_component_framework':False,'rows':rows}
save('verification.json',summary)
save('visual_qa.json',{'native_ui_check':'10 HTTP 200; 4 screenshots visually inspected','native_xlsx_check':'11 readiness rows; zero error cells; unconfirmed model fields blank; photos empty; configuration input-only','artifact_tool_readonly_render':{'pngs_written':3,'process_exit_code':1,'limitation':'All requested renders completed; process returned nonzero after render. No artifact-tool success exit claimed.'},'visual_review':'No clipped content in reviewed readiness/configuration/robot sheets or H12 Dual UI; no model facts displayed for blocked rows','live_facts_rendered':False})
print('10 honest live audit rows; separate RU guide verified; unchanged frozen dataset')
