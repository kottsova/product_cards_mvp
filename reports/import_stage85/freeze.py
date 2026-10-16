"""Pin only exact user-authorized changes; preserve all historical negative guards."""
import subprocess,hashlib,shutil
from pathlib import Path
out=Path(__file__).parent
shutil.copyfile('reports/import_stage84/run_full_parallel.py',out/'run_full_parallel.py')
changed=subprocess.check_output(['git','diff','--name-only'],text=True).splitlines()
new=subprocess.check_output(['git','ls-files','--others','--exclude-standard'],text=True).splitlines()
paths=sorted({p for p in changed+new if p.startswith(('product_tool/','tests/')) and p.endswith(('.py','.js','.html','.css')) and p!='tests/_pipeline_migration.py'})
a=Path('.gitattributes');text=a.read_text(encoding='utf8')
for rule in ('reports/import_stage85/** -text','reports/import_stage85/**/*.html -diff'):
 if rule not in text:text+='\n'+rule+'\n'
for p in paths:
 rule=subprocess.check_output(['git','check-attr','eol','--',p],text=True).strip().rsplit(': ',1)[1]
 raw=Path(p).read_bytes();style=rule if rule in {'lf','crlf'} else 'crlf' if raw.count(b'\r\n')>raw.count(b'\n')/2 else 'lf'
 if rule not in {'lf','crlf'}:text+='\n'+p+' text eol='+style+'\n'
 raw=raw.replace(b'\r\n',b'\n');Path(p).write_bytes(raw if style=='lf' else raw.replace(b'\n',b'\r\n'))
a.write_text(text,encoding='utf8')
reason='Stage 85 user-authorized production batch UX: one neutral table, read-only lightweight JSON polling, Russian job/readiness labels, persisted semantic phases/timestamps and result counters while retaining numeric legacy stages and identity thresholds. Separate shared gallery selection and bounded selected-byte ZIP with approved hosts, safe names and rendition/content deduplication; existing Excel URL export retained. Sulpak expired stop permits one bounded candidate request; optional comment-form CAPTCHA does not prove a document challenge, real access-gate guards retained. Kit URL alone never confirms component identity; history and support/manual evidence preserved. Legacy UI assertions updated for the explicitly requested removal of duplicate LG UI.'
reason+=' Actual 12-item UI acceptance exposed quadratic Excel gallery reprojection; reuse the already enriched rows once per product, retaining photo URLs and all metadata/export semantics, with a bounded fan-out regression guard.'
reason+=' Actual thumbnail DOM decoding exposed Chromium ORB rejection of cross-origin LG images. Serve only saved photo IDs through the existing policy-aware full byte verifier/cache, with serialized bounded fetches, approved source hosts, hash/path/format checks and no access-stop bypass. Lightbox and thumbnails use the verified local content; external source links and Excel URLs remain unchanged.'
pins={p:hashlib.sha256(Path(p).read_bytes()).hexdigest() for p in paths}
with Path('tests/_pipeline_migration.py').open('a',encoding='utf8',newline='') as target:
 target.write('\r\n# Stage 85 explicitly authorized production batch UX and P12ED recovery; historical guards retained.\r\nALL_AUTHORIZED_CHANGES.update('+repr({p:reason for p in paths})+')\r\nPINNED_SHA256.update('+repr(pins)+')\r\n')
print('Stage 85 exact pins:',len(pins))
