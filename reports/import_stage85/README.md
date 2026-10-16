# Stage 85 — production batch UX + P12ED dealer recovery

Verdict: **PASS**.

## P12ED / Sulpak

Old stop history is append-only. The historical S3WER challenge stop was active when row 172 ran. TTL already existed; the dealer diagnostics incorrectly kept citing the historical event without expiry context. The actual Stage 85 visible Chrome visit exposed the further root cause: optional review/comment CAPTCHA was being classified as a document access gate. The shared HTTP and attended classifiers now distinguish these optional controls; genuine access gates, 403/429, manual and fatal stops retain their guards.

After expiry: one fresh visible persistent Chrome navigation, HTTP 200, ordinary PDP, no challenge interaction. H1 / Product JSON-LD name: LG P12ED. Product ID 606431; canonical and Product URL contain both component strings, but content does not prove the two-unit relation. Exact kit remains unknown. The raw content audit found 41 raw fields / 29 image candidates; 0 accepted kit facts / photos. Row 172 now stores the actually inspected candidate; other official/support sources and documents are byte-for-byte unchanged as database records. See `sulpak_recovered_probe.json`, `sulpak_content_audit.json`, `capture_redactions.json`. Raw DOM is retained locally under data/stage85_raw; committed inspection copies redact tokens and non-data inline scripts.

## UI and persisted progress

Before: generic queue plus LG-only queue/table, repeated category lists, raw statuses, whole-HTML polling. After: one neutral table with selection, model/article, Russian statuses, current operation, accepted specs, confirmed-photo count, official color, readiness and actions. JSON GET /batches/{id}/progress performs only saved-state reads; 3-second polling changes cells/counters without replacing the document, scroll or selection. Job status and readiness are separate; queued readiness is —. All/none/queue/retry, prominent Excel, separate gallery/lightbox and selected-photo ZIP are available.

Each job retains queued_at, started_at, stage_started_at, finished_at, final_status, readiness, specs_count, photos_count, color and semantic phase. Legacy integer current_stage remains compatible; API current_stage is semantic. Actual extraction hooks and append-only phase events represent real operations; skipped phases are not fabricated. Manual checking is displayed as a discovery substage. Historical terminal results are backfilled once from saved evidence at startup; polling does not perform discovery or recalculate readiness.

## Real acceptance and recovered UI failures

Original 12-row LG upload and unchanged Stage 84 mixed input: actual UI upload → unedited confirmation → one bulk queue action → default production worker → automatic JSON progress → final table. The LG download attempt exposed quadratic gallery reprojection in Excel; it was fixed by reusing enriched rows once per product. LG downloads were resumed on the same completed batch without adding jobs. The original mixed UI flow completed end-to-end; an additional final-runtime download check is recorded separately in mixed/download_acceptance.json. Startup connection refusals and bounded localhost navigation/selection timeouts are retained in local diagnostic logs and are not counted as successful operations.

The separate rendering check exposed direct LG embedding rejected by Chromium ORB. Thumbnails/lightbox now serve verified bytes for saved photo IDs through the same bounded policy-aware image verifier/cache, with source host restrictions, image decoding, hash/path/size/MIME checks and serialized fetches. No browser security flags or CAPTCHA interactions were used. First eight actual thumbnails and the lightbox have positive decoded pixel dimensions; external links and Excel photo URLs are preserved. JPG/JPEG cache format aliases are both covered.

| Batch | Processed | Ready | With gaps | Not ready | Excel | Selected ZIP |
|---|---:|---:|---:|---:|---:|---:|
| LG original | 12/12 | 5 | 6 | 1 | 14.3s | 2 verified files, 2.8s |
| Mixed, 6 brands | 8/8 | 6 | 0 | 2 | 9.0s | 2 verified files, 19.1s |

Both ZIP downloads were opened, each image decoded with Pillow and dimensions/format/size/hash checked; duplicate bytes are excluded. ZIP uses safe Brand_Model_Article_photos.zip names and the highest available published rendition in each known alias group. A failed image/stop returns a visible error instead of a partial-success ZIP.

## LG final table

| ID | Model / article | Accepted specs | Confirmed photos | Readiness |
|---:|---|---:|---:|---|
| 184 | P12ED | 0 | 0 | Не готова |
| 185 | S3WER | 53 | 20 | Готова |
| 186 | MS2082F | 65 | 36 | Готова с пробелами |
| 187 | TW4V7EB1W | 108 | 64 | Готова с пробелами |
| 188 | GC-B459MLWM | 49 | 65 | Готова с пробелами |
| 189 | VK89309H | 42 | 62 | Готова |
| 190 | W4W8LVPKZHM | 175 | 30 | Готова с пробелами |
| 191 | 86NANO81A6A | 107 | 71 | Готова |
| 192 | RNC9 | 126 | 76 | Готова с пробелами |
| 193 | S40T | 35 | 59 | Готова |
| 194 | ON66 | 105 | 59 | Готова |
| 195 | ON77DK | 123 | 66 | Готова с пробелами |

## Stability

Five distinct brands were retried through the real UI on the corrected worker: LG, Apple, Xiaomi, Dreame, JBL. A second immediate retry click created no extra active jobs. 5/5 remained ready. Apple/Xiaomi/Dreame/JBL counts were unchanged; LG grew from 53/20 to 69/30 because Sulpak recovered and its page explicitly printed S3WER.ALWPCOM. Previously confirmed official sources were retained; no counts decreased. Phase history and saved evidence remained available. This business-path rerun preceded the isolated thumbnail delivery patch; actual thumbnail decoding and full regression were then checked on the final source.

## Regression

Full standard unittest discovery: 1949 tests / 119 modules, all OK; no omitted/duplicated modules, production bytes unchanged during the final run. Exact user-authorized source pins preserve all earlier negative pipeline guards. See final_regression.json and full_group_*.json/log. Earlier interrupted and pre-thumbnail runs are kept separately and do not qualify the final PASS.
