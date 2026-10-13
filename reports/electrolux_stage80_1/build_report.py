"""Controlled-use decision under the explicit Stage 80.1 qualification rule."""
import json,hashlib
from pathlib import Path
R=Path(__file__).parent
def read(p):return json.loads((R/p).read_text(encoding='utf8'))
full=read('release_live/summary.json');repeat=read('release_stability/summary.json');reg=read('regression_release.json');fault=read('fault_recovery_final_summary.json')
assert len(full['rows'])==10 and all(x['live_success'] for x in full['rows'])
assert len(repeat['rows'])>=5 and all(x['live_success'] and x['stable'] and not any(x['duplicates'].values()) for x in repeat['rows'])
assert full['context_closed'] and repeat['context_closed'] and fault['context_closed']
assert full['source_tree_unchanged'] and repeat['source_tree_unchanged']
assert reg['exit_code']==0 and reg['source_tree_unchanged']
assert (R/'dataset.json').read_bytes()==Path('reports/electrolux_stage78/dataset.json').read_bytes()
assert not fault['injected_timeout']['remaining_owned_processes']
assert fault['recovered_job']['readiness']['verdict']=='export_ready'
rows=[read(f'release_live/{x["id"]}/result.json') for x in full['rows']]
for pid in (1,2):
 x=next(x for x in rows if x['input']['id']==pid);assert x['readiness']['conflicts']==1 and x['readiness']['verdict']=='not_ready'
x=next(x for x in rows if x['input']['id']==10)
assert x['evidence']['identity']['requested_revision_identity_confirmed'] and not x['evidence']['identity']['configuration_confirmed'] and x['readiness']['confirmed_specs']==1 and x['readiness']['verdict']=='not_ready'
timing=[]
for phase in ('release_live','release_stability'):
 events=[json.loads(s) for s in (R/phase/'browser_timing.jsonl').read_text(encoding='utf8').splitlines()]
 nav=[x for x in events if x.get('phase')=='public_goto' and x.get('state')=='end']
 assert not any(x.get('timeout') or x.get('exception') for x in nav)
 timing.append({'phase':phase,'max_navigation_seconds':max(x['elapsed'] for x in nav),'navigation_calls':len(nav),'unexplained_stalls':0,'permanent_stages':sorted({x.get('source_type') for x in events if x.get('provider')=='timing'})})
q={'stage':'80.1','stage_pass':True,'qualification_rule':'Current bounded safeguards and live stability; historical unknown cause explicitly permitted by user','verdict':'Electrolux adapter production-ready for controlled use','scope':'Opt-in visible persistent Chrome binding in ordinary worker; same context per run, bounded recovery and access guards. Default HTTP is not claimed as the qualified transport.','historical_root_cause':'unobservable due to missing trace','known_limits':['EFI61141B native source ambiguity','EF7742OBI native source ambiguity','EOD6C46K2 insufficient exact-revision technical evidence'],'dataset_sha256':hashlib.sha256((R/'dataset.json').read_bytes()).hexdigest(),'actual_live_models':10,'usable_for_controlled_review':9,'ready_cards':7,'confirmed_specs':sum(x['specs'] for x in full['rows']),'confirmed_photos':sum(x['photos'] for x in full['rows']),'stability_models':len(repeat['rows']),'stability_pass':True,'regression':{k:reg[k] for k in ('exit_code','result','source_tree_unchanged')},'timing':timing,'injected_real_timeout_seconds':fault['injected_timeout']['seconds'],'remaining_owned_processes':0,'recovered_actual_live_model':fault['recovered_job']['model'],'false_revision_facts':0}
(R/'qualification.json').write_text(json.dumps(q,ensure_ascii=False,indent=2)+'\n',encoding='utf8',newline='\n')
text=['# Stage 80.1 — Electrolux qualification decision','',
'**PASS. Electrolux adapter production-ready for controlled use.**','',
'## 1. Historical stall — known / unknown',
'Historical root cause = unobservable due to missing trace. Known: 337.109513 с total, 23 с completed discovery trace, 314.109513 с unobserved after UK catalog. Missing original navigation/DOM starts and stack make the exact historical cause impossible to prove. No presumed cause is selected. Prior Stage 79/80 verdicts and failed attempt records remain historical evidence.','',
'Found systemic risk: synchronous browser driver/DOM/binary call had no external wall-clock bound. The existing isolated worker now bounds it and discards its owned process/context on timeout. Current safeguards qualify controlled use under the user’s Stage 80.1 rule, without pretending to reconstruct the old event.','',
'## 2. Safeguards / fault injection',
'Deterministic offline fixture runs an actual synchronous page.goto method that never returns despite the native timeout. Through ordinary worker.run_once: timeout ends first job as needs_review, logs stage/URL/job ID/reason and pre-timeout stack, skips external/dealer searches because availability is unknown, clears failed context, processes next job in a fresh context and succeeds on repeat without duplicate source.','',
'Tests also cover recovery budget, expired-product cleanup, persistent default diagnostics, rate-limit preservation, and observed 429 immediately persisted before a hanging navigation can reach DOM snapshot. Recovery does not remove host stops or automatically interact with CAPTCHA.','',
f'Real dedicated persistent Chrome smoke: artificial synchronous hang stopped in {q["injected_real_timeout_seconds"]:.3f} с; owned Python/Node/Chrome tree had zero remaining processes. Next ordinary job recovered fresh session/profile and obtained actual live EDHI618WD, 29 specs, export_ready. Synthetic failure is not counted as live success. fault_recovery_final_summary.json and its stack log retain proof.','',
'Budgets unchanged from Stage 80: native goto 10 с, outer navigation 18 с, snapshot 6 с, candidate 24 с, discovery 100 с, product 150 с, document fetch 12 с / batch 35 с, image batch 24 с. Process wall bounds cover driver calls; product/stage budgets are cooperative between bounded operations. Byte/page/DOM caps remain. No arbitrary Python CPU hard preemption is claimed.','',
'## 3. Permanent production telemetry',
'Existing worker opt-in flag: --electrolux-browser-profile PATH. Adapter-owned binding keeps research dispatch out of worker; existing single_worker lock, ordinary jobs/evidence/readiness/export and one persistent context are reused.','',
'Example: .venv/Scripts/python.exe -m product_tool.worker --data-dir data --electrolux-browser-profile data/electrolux_stage78_chrome_profile',
'The operator uses the foreground controlled worker as the single worker for that data directory. Existing 100-navigation/1800-second session caps and one technical recovery remain; controlled use is bounded, not an unlimited unattended session.','',
'Permanent files beside the data DB: electrolux_browser_timing.jsonl and electrolux_browser_timing.stack.log. SQLite discovery trace also retains job events. JSONL includes job/session IDs, start/end, discovery, navigation/status/DOM, extraction, documents, photos, persistence, skipped stages, timeout and recovery. Stack capture is armed before each driver call and cancelled on success. Cookie values are not logged/exported.','',
'## 4. Current live evidence / real gaps',
'Frozen Stage 78 dataset unchanged. Fresh PDP/inventory and byte fetches; same-run catalog cache is discovery-only, no replay replaces actual live.','',
'| Model | Specs | Photos | Readiness | Runtime s |','|---|---:|---:|---|---:|']
for x in full['rows']:text.append(f'| {x["model"]} | {x["specs"]} | {x["photos"]} | {x["readiness"]} | {x["seconds"]} |')
text+=['',f'10/10 actual live; 9/10 usable for review; 7/10 ready; {q["confirmed_specs"]} confirmed specs and {q["confirmed_photos"]} byte-verified selected photos. Manuals optional. Thresholds and model/configuration identity were not weakened.','',
'EFI61141B and EF7742OBI each retain one native source ambiguity: unequal Push Button Functions lists in the same FullSpecification/Other parent, without distinct semantic keys. No canonical split or conflict suppression. EOD6C46K2 retains one spec and one exact-owner image: 94949957800 identity proved; base-PDP technical/doc relation to revision still unknown. These three cards remain not_ready/needs_review as appropriate.','',
'EB71U1WB is now 37 specs rather than 39: current official source changed Maskintyp→Typ and the dimension label; 237×300×439 is retained as one composite fact instead of three axes. No replay facts restored. New full/repeat signatures are stable. eb71_live_delta.json contains the raw change.','',
'Repeat six categories in the same DB/profile:']
for x in repeat['rows']:text.append(f'- {x["model"]}: live={x["live_success"]}, stable={x["stable"]}, runtime={x["seconds"]} с, duplicates={x["duplicates"]}.')
text+=['','6/6 stable. Sources, PNC identity, values/units/conflicts, selected image bytes/dimensions, document bytes/language and readiness retained. Contexts closed.','',
'## 5–6. Verdict / regression / release',
'**Electrolux adapter production-ready for controlled use**, with two source ambiguities, one exact-revision evidence gap and historical cause unknown. Risk class is bounded by timeout/context recovery and permanent telemetry.','',
f'Full regression: {reg["result"]}, exit={reg["exit_code"]}, source_tree_unchanged={reg["source_tree_unchanged"]}. Preliminary failure was the existing research/worker architecture guard: direct transport imports were moved into adapter binding, guard was not weakened. Only regression_release is final. Targeted identity/session/guard tests and real Chrome recovery passed. Native UI 10 cards; Excel 15 sheets; formula errors 0; 19 verified photos and 29 identity-qualified PDFs.','',
'Stage 79–80.1 code and publishable evidence are committed together after PASS/regression/diff checks. Runtime DB/profile/local downloads follow existing ignore rules; privacy-only SSR redactions are verified not to change identity or fact acceptance. Publication and final Git verification artifacts distinguish local evidence from Git files. Commit hash and HEAD==origin/main/clean-tree confirmation are provided in the final response, avoiding a circular self-referencing commit file.','']
(R/'REPORT.md').write_text('\n'.join(text),encoding='utf8',newline='\n')
print({'pass':q['stage_pass'],'verdict':q['verdict'],'live':q['actual_live_models'],'specs':q['confirmed_specs'],'photos':q['confirmed_photos'],'repeat':q['stability_models'],'timing':timing})
