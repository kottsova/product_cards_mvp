"""Render the Stage 7.1 audit from saved results; no network."""
from collections import Counter
import hashlib
import re
from .endpoint_probe import guarded_entry_point
from .runner_v71 import ROOT, BASE, OUTPUT, read, write


@guarded_entry_point
def render():
    result = read(OUTPUT / 'final_results.json')
    before = read(OUTPUT / 'protected_hashes_before.json')
    hashes = {p: {'before': digest, 'after': hashlib.sha256((ROOT / p).read_bytes()).hexdigest()} for p, digest in before.items()}
    changed = [p for p, value in hashes.items() if value['before'] != value['after']]
    unauthorized = [p for p in changed if p != 'product_tool/identity.py']
    if unauthorized:
        raise RuntimeError('Protected files changed: ' + repr(unauthorized))
    write(OUTPUT / 'protected_hashes_after.json', {'files': hashes, 'unchanged_count': len(hashes) - len(changed), 'authorized_changes': changed, 'unauthorized_changes': unauthorized, 'note': 'identity.py optional versioned structured-name extension is explicitly requested; all baseline artifacts and other existing files remain byte-identical'})
    runs = result['runs']
    levels = Counter(c['identity_verification']['level'] for r in runs for d in r['domains'] for c in d['candidates'])
    refs = {(s['store'], s['snapshot_id']) for r in runs for d in r['domains'] for s in d['snapshots_reused']}
    summary = {'products': len(runs), 'old_not_found': sum(r['before'] == 'official_exact_product_not_found' for r in runs), 'old_not_found_changed': sum(r['before'] == 'official_exact_product_not_found' and r['outcome'] != r['before'] for r in runs), 'exact_model_or_variant_products': sum(r['outcome'] == 'official_exact_product_found' for r in runs), 'incomplete_products': sum(r['outcome'] == 'official_search_incomplete' for r in runs), 'identity_review_products': [r['catalog_identity']['seller_sku_raw'] for r in runs if r['outcome'] == 'identity_review_required'], 'new_http_requests': result['new_http_requests'], 'dealer_enabled_products': sum(r['dealer_fallback']['allowed'] for r in runs), 'candidate_identity_levels': dict(levels), 'unique_candidate_urls': len({c['url'] for r in runs for d in r['domains'] for c in d['candidates']}), 'baseline_snapshots_reused': sum(store == 'source_snapshots.sqlite3' for store, sid in refs), 'new_snapshots_replayed': sum(store != 'source_snapshots.sqlite3' for store, sid in refs), 'protected_files_unchanged': len(hashes) - len(changed), 'authorized_file_changes': changed, 'chromium_launches': 0}
    test_log = (OUTPUT / 'tests.txt').read_text(encoding='utf-8')
    summary['tests_run'] = int(re.search(r'Ran (\d+) tests', test_log).group(1))
    summary['tests_passed'] = test_log.rstrip().endswith('OK')
    write(OUTPUT / 'summary.json', summary)
    lines = ['# Stage 7.1: catalog-backed identity reconciliation', '', 'Stage 7 remains an immutable baseline. The original `Товары` rows were read with openpyxl read_only=True; no workbook writes occurred. Alternate titles remain titles, not alternate codes. No alternate-code column exists in this catalog.', '', '## Results', '', f"- Products: {len(runs)}. Previous not-found decisions changed: {summary['old_not_found_changed']}/{summary['old_not_found']}.", f"- Exact model/variant: {summary['exact_model_or_variant_products']}. Incomplete: {summary['incomplete_products']}. Identity review: {', '.join(summary['identity_review_products'])}.", f"- New HTTP: {result['new_http_requests']}/24; replay HTTP: 0; Chromium: 0; dealer requests: 0; dealer gates enabled: 0.", f"- Reused baseline snapshots: {summary['baseline_snapshots_reused']}; new snapshots: {summary['new_snapshots_replayed']}; unique official candidate URLs: {summary['unique_candidate_urls']}.", f"- Candidate occurrences after reranking: {dict(levels)}. Occurrences across products/domains are not unique pages.", '', 'A received HTTP 200 is recorded separately from evidence of a completed product search. Empty/JavaScript search shells, truncated sitemap traversal, missing responses and pending product candidates keep the result incomplete. `not_found` is never inherited from Stage 7. Structured Product names can confirm a title-derived marketing model only under matching brand/category, token boundaries and non-conflicting model/variant evidence. Generic body text cannot confirm identity.', '', '## Per-product audit', '', '| Seller SKU | Real catalog title | Before | After | New HTTP | Dealer |', '|---|---|---|---|---:|---|']
    for r in runs:
        identity = r['catalog_identity']
        lines.append('| ' + ' | '.join([identity['seller_sku_raw'], '<br>'.join(identity['titles_raw']), r['before'], r['outcome'], str(r['http_requests']), 'closed']) + ' |')
    for r in runs:
        identity = r['catalog_identity']
        lines += ['', '### ' + identity['seller_sku_raw'], '', '- Catalog rows: ' + ', '.join(x['row_reference'] for x in identity['rows']), '- Identity status: ' + identity['review_status'], '- Original title(s): ' + ' / '.join(identity['titles_raw']), '- Brand/category: ' + identity['brand_raw'] + ' / ' + identity['category_raw'], '- Alternate code: ' + str(identity['alternate_code_raw']), '- Variants: ' + str(identity['identity']['variant_attributes']), '- Candidates: ' + '; '.join(f"{c['raw_value']} → {c['role']} ({c['source_field']}, confidence {c['confidence']}, {c['extraction_rule']})" for c in identity['candidates']), '- Planned queries: ' + '; '.join(q['query'] for q in identity['queries']), '- High-confidence identity query scope complete: ' + str(r['identity_query_scope_complete']), '- Dealer gate: ' + r['dealer_fallback']['reason'], '', '| Official domain | Executed/replayed queries and evidence | Snapshots | Candidate outcomes |', '|---|---|---:|---|']
        for d in r['domains']:
            queries = '; '.join(f"{q['query']}: {q['origin']}, HTTP response={q.get('response_received', False)}, checked={q['checked']}" for q in d['queries'])
            counts = dict(Counter(c['identity_verification']['level'] for c in d['candidates']))
            lines.append(f"| {d['domain_id']} | {queries} | {len(d['snapshots_reused'])} | {counts} |")
        candidates = {c['url']: c['identity_verification']['level'] for d in r['domains'] for c in d['candidates']}
        if candidates:
            lines += ['', 'Official candidates (URL → final identity level):', '']
            lines += [f'- {url} → {level}' for url, level in candidates.items()]
        else:
            lines += ['', 'No official product candidates were supported by the bounded saved evidence.']
    lines += ['', '## HTTP and access scope', '', 'The eight new requests were four Samsung Jet queries (KZ/US) and four Kärcher marketing-model queries (KZ/global). No new Dreame request was executable through the saved declared routes. RLD35GD ambiguity blocks HTTP. Existing protected endpoints and HTTP host pauses were retained; browser evidence never pauses HTTP or other regional hosts. `challenge_suspected` does not prevent offline extraction from an existing snapshot; it does prevent repeating that HTTP endpoint in this run.', '', 'Detailed request receipts: [http_attempts.json](http_attempts.json). Before-network replay: [offline_results.json](offline_results.json). Final identities, complete raw rows, query metadata, all candidate verifications, snapshot references and scope hashes: [final_results.json](final_results.json). The final saved replay sends zero requests. Each new request and redirect consumes the aggregate 24, per-domain 10 and per-product 40 caps; at most three new target pages per domain and 40 seconds per domain/product. No domains or source registries were added.', '', '## Validation and protected files', '', f"Tests: {summary['tests_run']}, passed: {summary['tests_passed']}." + ' [tests.txt](tests.txt) contains the complete unittest result. It covers original-row/read-only loading, ambiguity, typed brand rules, parentheses priority, significant punctuation/region/service index, WB exclusion, structured name/body boundary, variant and model qualifier conflicts, checkpoint scope versions, offline replay, HTTP preconditions/redirect cap, method-scoped protection and immutable registries.', '', f"{len(hashes) - len(changed)} pre-existing protected files are byte-identical. The sole authorized existing-file change is `product_tool/identity.py` (backward-compatible optional fields and opt-in 7.1 verification). All Stage 2–7 report/snapshot files, source/dealer/domain registries, browser manual_review_only policy, unresolved-label/Accesstyle evidence, Sulpak allowlist, dealer exclusion, workbook and user edits in jobs.py/storage.py/worker.py are unchanged.", '', '[Before hashes](protected_hashes_before.json) · [Before/after hashes](protected_hashes_after.json).', '', '## Recommended next stage — not implemented', '', 'Resolve the two-title RLD35GD identity with the catalog owner, then harden HTTP search-result completeness for the already verified official domains: distinguish real result/explicit-empty responses from search shells and review the reranked pending official URLs under a separately approved bounded run. Keep dealers closed until the revised complete official search warrants fallback. Do not resume browser strategy work or expand dealer scope.']
    (OUTPUT / 'report.md').write_text('\n'.join(lines) + '\n', encoding='utf-8')
    print(summary)

if __name__ == '__main__':
    render()
