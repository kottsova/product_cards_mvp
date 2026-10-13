# Stage 80.1 — Electrolux qualification decision

**PASS. Electrolux adapter production-ready for controlled use.**

## 1. Historical stall — known / unknown
Historical root cause = unobservable due to missing trace. Known: 337.109513 с total, 23 с completed discovery trace, 314.109513 с unobserved after UK catalog. Missing original navigation/DOM starts and stack make the exact historical cause impossible to prove. No presumed cause is selected. Prior Stage 79/80 verdicts and failed attempt records remain historical evidence.

Found systemic risk: synchronous browser driver/DOM/binary call had no external wall-clock bound. The existing isolated worker now bounds it and discards its owned process/context on timeout. Current safeguards qualify controlled use under the user’s Stage 80.1 rule, without pretending to reconstruct the old event.

## 2. Safeguards / fault injection
Deterministic offline fixture runs an actual synchronous page.goto method that never returns despite the native timeout. Through ordinary worker.run_once: timeout ends first job as needs_review, logs stage/URL/job ID/reason and pre-timeout stack, skips external/dealer searches because availability is unknown, clears failed context, processes next job in a fresh context and succeeds on repeat without duplicate source.

Tests also cover recovery budget, expired-product cleanup, persistent default diagnostics, rate-limit preservation, and observed 429 immediately persisted before a hanging navigation can reach DOM snapshot. Recovery does not remove host stops or automatically interact with CAPTCHA.

Real dedicated persistent Chrome smoke: artificial synchronous hang stopped in 1.373 с; owned Python/Node/Chrome tree had zero remaining processes. Next ordinary job recovered fresh session/profile and obtained actual live EDHI618WD, 29 specs, export_ready. Synthetic failure is not counted as live success. fault_recovery_final_summary.json and its stack log retain proof.

Budgets unchanged from Stage 80: native goto 10 с, outer navigation 18 с, snapshot 6 с, candidate 24 с, discovery 100 с, product 150 с, document fetch 12 с / batch 35 с, image batch 24 с. Process wall bounds cover driver calls; product/stage budgets are cooperative between bounded operations. Byte/page/DOM caps remain. No arbitrary Python CPU hard preemption is claimed.

## 3. Permanent production telemetry
Existing worker opt-in flag: --electrolux-browser-profile PATH. Adapter-owned binding keeps research dispatch out of worker; existing single_worker lock, ordinary jobs/evidence/readiness/export and one persistent context are reused.

Example: .venv/Scripts/python.exe -m product_tool.worker --data-dir data --electrolux-browser-profile data/electrolux_stage78_chrome_profile
The operator uses the foreground controlled worker as the single worker for that data directory. Existing 100-navigation/1800-second session caps and one technical recovery remain; controlled use is bounded, not an unlimited unattended session.

Permanent files beside the data DB: electrolux_browser_timing.jsonl and electrolux_browser_timing.stack.log. SQLite discovery trace also retains job events. JSONL includes job/session IDs, start/end, discovery, navigation/status/DOM, extraction, documents, photos, persistence, skipped stages, timeout and recovery. Stack capture is armed before each driver call and cancelled on success. Cookie values are not logged/exported.

## 4. Current live evidence / real gaps
Frozen Stage 78 dataset unchanged. Fresh PDP/inventory and byte fetches; same-run catalog cache is discovery-only, no replay replaces actual live.

| Model | Specs | Photos | Readiness | Runtime s |
|---|---:|---:|---|---:|
| EFI61141B | 17 | 2 | not_ready | 69.18 |
| EF7742OBI | 29 | 2 | not_ready | 66.61 |
| EDHI618WD | 29 | 2 | export_ready | 57.28 |
| E52LE100S | 34 | 2 | export_ready | 27.66 |
| LNT6TE18S5 | 40 | 2 | export_ready | 33.54 |
| EOF6P46X | 39 | 2 | export_ready | 29.05 |
| EIV84550 | 27 | 2 | export_ready | 20.98 |
| EB71U1WB | 37 | 2 | export_ready | 75.87 |
| EWD746PCBI | 30 | 2 | export_ready | 31.18 |
| EOD6C46K2 | 1 | 1 | not_ready | 36.21 |

10/10 actual live; 9/10 usable for review; 7/10 ready; 283 confirmed specs and 19 byte-verified selected photos. Manuals optional. Thresholds and model/configuration identity were not weakened.

EFI61141B and EF7742OBI each retain one native source ambiguity: unequal Push Button Functions lists in the same FullSpecification/Other parent, without distinct semantic keys. No canonical split or conflict suppression. EOD6C46K2 retains one spec and one exact-owner image: 94949957800 identity proved; base-PDP technical/doc relation to revision still unknown. These three cards remain not_ready/needs_review as appropriate.

EB71U1WB is now 37 specs rather than 39: current official source changed Maskintyp→Typ and the dimension label; 237×300×439 is retained as one composite fact instead of three axes. No replay facts restored. New full/repeat signatures are stable. eb71_live_delta.json contains the raw change.

Repeat six categories in the same DB/profile:
- EFI61141B: live=True, stable=True, runtime=71.32 с, duplicates={'sources': 0, 'photos': 0, 'documents': 0}.
- EDHI618WD: live=True, stable=True, runtime=74.25 с, duplicates={'sources': 0, 'photos': 0, 'documents': 0}.
- E52LE100S: live=True, stable=True, runtime=24.38 с, duplicates={'sources': 0, 'photos': 0, 'documents': 0}.
- EIV84550: live=True, stable=True, runtime=20.11 с, duplicates={'sources': 0, 'photos': 0, 'documents': 0}.
- EB71U1WB: live=True, stable=True, runtime=69.78 с, duplicates={'sources': 0, 'photos': 0, 'documents': 0}.
- EOD6C46K2: live=True, stable=True, runtime=35.98 с, duplicates={'sources': 0, 'photos': 0, 'documents': 0}.

6/6 stable. Sources, PNC identity, values/units/conflicts, selected image bytes/dimensions, document bytes/language and readiness retained. Contexts closed.

## 5–6. Verdict / regression / release
**Electrolux adapter production-ready for controlled use**, with two source ambiguities, one exact-revision evidence gap and historical cause unknown. Risk class is bounded by timeout/context recovery and permanent telemetry.

Full regression: ['Ran 1879 tests in 641.548s', 'OK'], exit=0, source_tree_unchanged=True. Preliminary failure was the existing research/worker architecture guard: direct transport imports were moved into adapter binding, guard was not weakened. Only regression_release is final. Targeted identity/session/guard tests and real Chrome recovery passed. Native UI 10 cards; Excel 15 sheets; formula errors 0; 19 verified photos and 29 identity-qualified PDFs.

Stage 79–80.1 code and publishable evidence are committed together after PASS/regression/diff checks. Runtime DB/profile/local downloads follow existing ignore rules; privacy-only SSR redactions are verified not to change identity or fact acceptance. Publication and final Git verification artifacts distinguish local evidence from Git files. Commit hash and HEAD==origin/main/clean-tree confirmation are provided in the final response, avoiding a circular self-referencing commit file.
