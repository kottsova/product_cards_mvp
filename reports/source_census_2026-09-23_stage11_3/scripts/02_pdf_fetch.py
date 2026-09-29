"""Stage 11.3 phase 2 -- bounded, Range-aware, completeness-classified fetch
of the user-provided PDF (Stage 8.6 mechanism), independent of whether the
DNS product page itself was reachable."""
import json

from lib import OUT, load_budget, make_probe, fetch_bytes_bounded

budget = load_budget()
allowed_hosts = tuple(budget['allowed_hosts'])
probe = make_probe(budget)

url = 'https://drv.dns-shop.ru/drivers/Manuals/H/hyperx-quadcast-2-s_instrukcia_104913_30102025.pdf'
counter = {'n': 0}
result, log_entries = fetch_bytes_bounded(
    probe.session, probe.policy, url, allowed_hosts,
    chunk_bytes=budget['limits']['pdf_chunk_bytes'],
    max_total_bytes=budget['limits']['pdf_max_total_bytes'],
    request_counter=counter,
    accept='application/pdf,*/*;q=0.1',
)

output = {
    'phase': 'pdf_fetch',
    'url': url,
    'completeness': result['completeness'],
    'reason': result.get('reason'),
    'declared_total_bytes': result.get('declared_total_bytes'),
    'bytes_assembled': result.get('bytes_assembled'),
    'request_log': log_entries,
}
(OUT / 'phase2_pdf_fetch.json').write_text(json.dumps(output, indent=2, ensure_ascii=False), encoding='utf-8')

# Save bytes to scratch only (outside repo), not to reports/, per no-raw-content rule.
if result.get('bytes'):
    import pathlib
    scratch_dir = pathlib.Path(r'C:\Users\Julynce\AppData\Local\Temp\claude\a--work-dev-product-cards-mvp\1741bb85-29db-47a4-97a9-ed84155ebc47\scratchpad\stage11_3_pdf')
    scratch_dir.mkdir(parents=True, exist_ok=True)
    (scratch_dir / 'hyperx_quadcast_2s_instrukcia.pdf').write_bytes(result['bytes'])
    print('saved to scratch, bytes:', len(result['bytes']))

print(json.dumps({k: v for k, v in output.items() if k != 'request_log'}, indent=2, ensure_ascii=False))
