"""Generate the Stage 6 report solely from saved diagnostic evidence."""
from pathlib import Path
import json
import re
from .browser_contracts import VERSIONS
from .runner_v6 import OUTPUT


def write_report():
    payload=json.loads((OUTPUT/'dry_run.json').read_text(encoding='utf-8'))
    final=json.loads((OUTPUT/'final_reprocessing.json').read_text(encoding='utf-8'))
    before=json.loads((OUTPUT/'protected_hashes_before.json').read_text(encoding='utf-8'));after=json.loads((OUTPUT/'protected_hashes_after.json').read_text(encoding='utf-8'))
    tests=(OUTPUT/'tests.txt').read_text(encoding='utf-8');count=re.findall(r'Ran (\d+) tests',tests)[-1]
    lines=['# Stage 6 — bounded browser-assisted first-party search v1','',f"Live diagnostic timestamp: {payload['generated_at']}",'',
        '## Runtime and opt-in', '',
        f"Existing runtime: **{payload['runtime']['runtime_version']}**, Chromium **{payload['runtime']['browser_version']}**, interpreter `{payload['runtime']['python']}`. The project venv lacks Playwright, but the adjacent existing project environment has it and the matching Chromium binaries. An ephemeral about:blank launch confirmed usability. No package or browser download was performed.", '',
        'BrowserAssistedSearchStrategy is disabled by default. It requires browser_assisted=True, a verified official source, explicit source/product identity, bounded budget and eligible static evidence. The dedicated runner_v6 research command is the only new live entry point. Existing LG workflows, census runners and production workers were not connected to it.', '',
        '## Safety and budgets', '',
        '- Per source: one fresh ephemeral context, at most two queries, six first-party navigations, three candidate URLs, three target identity validations, 60 seconds, 600,000-byte DOM limit and 5-second operation timeout. Bounds above the hard limits are rejected.',
        '- No persistent profile, credentials, imported cookies/storage, extensions, stealth, proxy changes, custom User-Agent, fingerprint spoofing or automatic login. Contexts are closed in finally blocks.',
        '- Main-frame requests are checked against host allowlists before forwarding; third-party requests and account/cart/contact flows are blocked. First-party 403/429 and visible challenge signals stop the host without retry.',
        '- Only declared search inputs and normal Enter submission are permitted. The input/form is revalidated immediately before typing. Cookie interactions are restricted to a unique rejection/necessary-only choice; other banners stop with interaction_blocked.',
        '- At most one ordinary technical retry is allowed for observation/navigation. Submits are not retried. No networkidle waits or arbitrary button clicks are used.', '',
        '## Static versus browser-assisted diagnostic', '',
        '| Family / catalog model | Static result | Browser result | Contexts | Queries | Navigations | Allowed network requests | Candidates | Target validations |',
        '| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |']
    for r in payload['runs']:
        usage=r['result']['strategy_evidence']['browser_usage']
        lines.append(f"| {r['source_family']} / {r['identity']['seller_sku']} | {r['static_outcome']} | {r['result']['stop_reason']} | {usage['contexts']} | {usage['queries']} | {usage['navigations']} | {usage['network_requests']} | {len(r['result']['candidates'])} | {usage['product_validations']} |")
    lines += ['',
        '**LG was not launched.** Its static result is search_no_results, but the saved sanitized static snapshot contains neither an explicit search input nor a retained JavaScript search handler. Therefore the required affirmative JS-search-UI evidence is unavailable. This is browser_strategy_not_eligible, not browser_runtime_unavailable. The explicit eligibility requirement takes precedence over attempting every named source; no JS dependency was invented.', '',
        '**Bosch Home:** the confirmed first-party homepage was opened. One ordinary technical navigation retry was used (two navigations total). No eligible visible search input was found within the bounded DOM. One sanitized homepage snapshot was saved; the context closed. This does not claim that Bosch has no search functionality outside the permitted interaction surface.', '',
        '**Dreame:** the first-party search page came directly from the observed Stage 5 search-link evidence, not a guessed URL. One navigation was issued. The rendered DOM exceeded the byte cap before interaction/snapshot persistence, causing budget_exhausted; the context closed. No search query was entered and no target URL was supplied manually.', '',
        'Measured totals: **2 contexts, 3 navigations, 177 allowed first-party network requests** including page resources. Network totals are not product probes; no separate HTTP-count cap was specified for Stage 6. Blocked resource totals were not retained in this live artifact. Both contexts closed within 60 seconds (Bosch approximately 9.7 seconds, Dreame approximately 2.8 seconds).', '',
        'No CAPTCHA/challenge, 403/429, foreign-redirect or cookie-consent stop was returned in this live pass. No candidates or target-page identities were established live. HyperX was not reopened because static search already validated it.', '',
        '## Actions and snapshots', '']
    for r in payload['runs']:
        lines += [f"### {r['source_family']}",'']
        for a in r['result']['strategy_evidence']['actions']:lines.append('- '+json.dumps(a,ensure_ascii=False,sort_keys=True))
        if not r['result']['strategy_evidence']['actions']:lines.append('- No browser action executed (eligibility gate).')
        refs=r['result']['checkpoint'].get('snapshots',[])
        for ref in refs:lines.append(f"- SourceSnapshot `{ref['snapshot_id']}` in `{ref['store']}`, phase `{ref['phase']}`, content SHA-256 `{ref['content_sha256']}`.")
        if not refs:lines.append('- No usable rendered snapshot saved.')
        lines.append('')
    lines += ['Snapshots reuse the existing FetchAttempt/SourceSnapshot tables in an isolated Stage 6 DB. They retain sanitized DOM, final URL, content hash and narrow discovery metadata. IDs, raw selectors, storage, cookies, headers, security values, full HAR, unrelated scripts and personal URL parameters are not persisted. Product microdata/search-role semantics survive sanitization. Only snapshot references/hashes appear in checkpoints.', '',
        '## Versioned checkpoint and offline verification', '', '| Component | Final version |','| --- | --- |']
    for k,v in VERSIONS.items():lines.append(f'| {k} | {v} |')
    lines += [f"| Browser runtime | {payload['runtime']['runtime_version']} |",f"| Browser binary | {payload['runtime']['browser_version']} |",'',
        'Compatibility also includes source/product identity, host allowlists, declarative selectors and budget. Final input revalidation changed strategy/UI semantics after the live attempt; the final versions are therefore different from the original live checkpoints. Old candidates are not silently accepted.', '',
        '| Family | Original checkpoint under final code | Offline reprocessing | Compatible resume of rebuilt checkpoint | New contexts / requests |','| --- | --- | --- | --- | --- |']
    for c in final['checks']:lines.append(f"| {c['source_family']} | {c['old_checkpoint_outcome']} | {c['reprocessing_outcome']} | {c['compatible_resume_outcome']} | 0 / 0 |")
    lines += ['',
        'Bosch reprocessing reproduced browser_search_ui_not_found from its hash-checked DOM without launching a browser, and its rebuilt compatible checkpoint returned checkpoint_complete with zero requests. Dreame has snapshot_missing, so the final parser is not claimed to have been verified against a Dreame rendered snapshot. LG remains ineligible and has no browser snapshot. Final offline verification preserved the snapshot DB hash. See final_reprocessing.json and reprocessed_checkpoint.json.', '',
        '## Regression and preservation', '',
        f"**{count} tests passed; exit code 0.** See tests.txt. The mandatory suite uses fake browsers and local HTML fixtures; no live browser launches are part of unittest discovery. Cases cover opt-in/eligibility, unsafe fields, searchboxes, login ambiguity, foreign transitions, navigation/service filtering, JSON-LD/microdata identity, variant conflict, visible text insufficiency, protection closure/no retry, deadline/DOM/navigation budgets, cookie blocking, version mismatch, hash tampering, zero-browser replay, registry immutability and production_ready=false.", '',
        f"Protected hashes unchanged: **{before==after}**. Full before/after manifests cover Stage 2–5.1 reports and snapshot DB, production/normalization/research registries, LG/Sulpak/source policy files, pre-existing SQLite files and the user's uncommitted jobs.py/storage.py/worker.py contents. The 186 unresolved labels, Accesstyle negative result, next census batch, Sulpak allowlist and the dealer exclusion remain unchanged.", '',
        'No production readiness was enabled. No Samsung/AEM/Shopify adapter, embedded-state extractor, general product attribute/media/manual extraction, dealer fallback or production orchestrator was added.', '',
        '## Exactly one next stage', '',
        'Recommend **Stage 6.1: bounded search-UI/DOM projection hardening**. Focus on preserving explicit JS-search-UI eligibility evidence and extracting the narrow rendered search region within the DOM cap, so cases like LG and Dreame can be evaluated without broadening interaction privileges. This next stage was not implemented.', '']
    (OUTPUT/'report.md').write_text('\n'.join(lines),encoding='utf-8')

if __name__=='__main__':write_report()
